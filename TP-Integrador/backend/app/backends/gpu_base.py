"""Base común de los backends GPU (CUDA y OpenCL).

Patrones:
- Template Method (segundo nivel): ``GpuBackend`` implementa una sola vez los
  pasos de ``BaseBackend`` (qué kernels se lanzan, con qué grillas y en qué
  orden, design D2 y D4 del cambio 2). Cada API implementa solo las primitivas:
  reservar y liberar buffers, copiar, lanzar un kernel, registrar un marcador y
  sincronizar. Así CUDA y OpenCL ejecutan exactamente la misma secuencia.
- Observer diferido: ``DeferredProgressReporter`` registra un marcador en la
  cola/stream por cada aviso de progreso y recién lo reenvía cuando el
  dispositivo llega a ese punto (design D4). Como todo ya está encolado,
  esperar no deja a la GPU ociosa entre bloques.
"""

import time
from abc import abstractmethod
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, nullcontext
from typing import Any, Protocol

import numpy as np

from app.core.backend import BaseBackend, OutOfMemoryError, ProgressCallback, ProgressReporter, StepProgress
from app.core.constants import (
  BLOCK_1D,
  CELL_PX,
  COMPOSE_TILE,
  DESC_DIM,
  DESC_GRID,
  FLOAT32_BYTES,
  INT32_BYTES,
  MATMUL_TILE,
  RGB_CHANNELS,
  TOPK_THREADS,
)
from app.core.job import MosaicJob
from app.core.params import MosaicParams
from app.core.result import MosaicResult, Stage
from app.core.timing import StageTimer, elapsed_ms_since

# Motivos cortos de indisponibilidad (spec deteccion-de-backends).
REASON_NO_CUDA_DEVICES = "sin dispositivos CUDA"
REASON_NO_OPENCL_GPU = "sin GPU OpenCL"
REASON_KERNEL_BUILD = "error de compilación de kernels"
# Aviso que acompaña al estado de todo backend GPU.
GPU_NUMERIC_WARNING = "float32 con FMA y funciones matemáticas del driver: puede diferir de CPU en casi-empates"
# Aviso del resultado cuando no se pudo reservar memoria page-locked (spec backend-cuda).
NOTE_PAGEABLE_TRANSFER = "transferencia sin memoria pinned"
# Mensaje de error cuando ni un bloque mínimo del matching entra en la memoria.
OUT_OF_MEMORY_MESSAGE = "memoria insuficiente"

# Kernels de kernels/mosaic.cu y kernels/mosaic.cl.
KERNEL_NAMES = (
  "resize_tiles",
  "tile_descriptors",
  "cell_descriptors",
  "sq_norms",
  "distances_tiled",
  "topk_rows",
  "compose",
)
# Entradas que viajan host → device, en el orden en que se copian.
INPUT_NAMES = ("tiles_src", "target_src", "choice")
# Buffer de la matriz parcial de distancias [m_chunk, N].
DIST_BUFFER = "dist"

Grid = tuple[int, ...]


class GpuStageTimer(StageTimer, Protocol):
  """Timer de GPU: además de las etapas, suma tiempos medidos en el host (copias a staging)."""

  def record_host(self, stage: Stage, elapsed_ms: float) -> None:
    """Suma a ``stage`` un tiempo medido con reloj de pared en el host."""


def ceil_div(numerator: int, denominator: int) -> int:
  """División entera redondeando hacia arriba."""
  return -(-numerator // denominator)


def job_buffer_sizes(job: MosaicJob) -> dict[str, int]:
  """Bytes de cada buffer del dispositivo de un trabajo, salvo la matriz de distancias."""
  n_tiles, n_cells, k, tile_px = job.n_tiles, job.n_cells, job.params.k, job.params.tile_px
  return {
    "tiles_src": job.tiles_src.nbytes,
    "target_src": job.target_src.nbytes,
    "choice": job.choice.nbytes,
    "tiles_px": n_tiles * tile_px * tile_px * RGB_CHANNELS,
    "tile_desc": n_tiles * DESC_DIM * FLOAT32_BYTES,
    "tile_norms": n_tiles * FLOAT32_BYTES,
    "cell_desc": n_cells * DESC_DIM * FLOAT32_BYTES,
    "cell_norms": n_cells * FLOAT32_BYTES,
    "topk_idx": n_cells * k * INT32_BYTES,
    "topk_dist": n_cells * k * FLOAT32_BYTES,
    "image": int(np.prod(job.output_shape)),
  }


def matching_chunk_rows(available_bytes: int, n_tiles: int, n_cells: int, max_alloc_bytes: int | None = None) -> int:
  """Celdas por bloque del matching (design D6).

  Usa la memoria disponible (y, si se informa, la reserva individual máxima del
  dispositivo), redondea hacia abajo a múltiplo de ``MATMUL_TILE`` y acota por
  M. Falla con "memoria insuficiente" si ni un bloque mínimo entra.
  """
  budget = available_bytes if max_alloc_bytes is None else min(available_bytes, max_alloc_bytes)
  rows_fit = max(0, budget) // (n_tiles * FLOAT32_BYTES)
  if rows_fit >= n_cells:
    return n_cells
  rows = rows_fit // MATMUL_TILE * MATMUL_TILE
  if rows == 0:
    raise OutOfMemoryError(
      f"{OUT_OF_MEMORY_MESSAGE}: ni un bloque de {MATMUL_TILE} celdas del matching entra en la GPU"
    )
  return rows


def pack_inputs(staging: np.ndarray, job: MosaicJob) -> Iterator[tuple[str, int, int]]:
  """Copia las entradas, una tras otra, al staging de bytes; devuelve (nombre, offset, bytes)."""
  offset = 0
  for name in INPUT_NAMES:
    data = getattr(job, name).reshape(-1).view(np.uint8)
    staging[offset : offset + data.nbytes] = data
    yield name, offset, data.nbytes
    offset += data.nbytes


def int_arg(value: int) -> np.int32:
  """Argumento entero de un kernel (int de 32 bits en C)."""
  return np.int32(value)


class DeferredProgressReporter(ProgressReporter):
  """Reenvía el progreso cuando el dispositivo alcanza cada punto encolado."""

  def __init__(
    self, on_progress: ProgressCallback | None, record_marker: Callable[[], Any], wait_marker: Callable[[Any], None]
  ) -> None:
    """Recibe las primitivas de la API para registrar un marcador y esperarlo."""
    super().__init__(on_progress)
    self._record_marker = record_marker
    self._wait_marker = wait_marker
    self._pending: list[tuple[Any, Stage, float]] = []

  def report(self, stage: Stage, fraction: float) -> None:
    """Registra un marcador en la cola; sin observador no hace nada."""
    if self._on_progress is not None:
      self._pending.append((self._record_marker(), stage, fraction))

  def drain(self) -> None:
    """Espera los marcadores en orden y reenvía cada aviso apenas se cumple."""
    for marker, stage, fraction in self._pending:
      self._wait_marker(marker)
      super().report(stage, fraction)
    self._pending.clear()


class GpuBackend(BaseBackend):
  """Pasos comunes de CUDA y OpenCL; cada API implementa las primitivas."""

  warnings = (GPU_NUMERIC_WARNING,)

  def __init__(self, device_name: str, chunk_cells: int | None = None) -> None:
    """``chunk_cells`` fuerza el tamaño de bloque del matching (tests)."""
    super().__init__(device_name)
    self.chunk_cells = chunk_cells
    self._progress = DeferredProgressReporter(None, self._record_marker, self._wait_marker)
    self._m_chunk = 0

  # --- Operaciones públicas (con la GPU activa) -------------------------------------

  def warmup(self) -> float:
    """Compila los kernels y ejecuta un trabajo mínimo; devuelve su duración en ms."""
    with self._active():
      return super().warmup()

  def run(self, tiles_src, target_src, params, choice, on_progress=None) -> MosaicResult:
    """Ejecuta un trabajo (ver ``BaseBackend.run``)."""
    with self._active():
      return super().run(tiles_src, target_src, params, choice, on_progress)

  def read_descriptors(
    self, tiles_src: np.ndarray, target_src: np.ndarray, params: MosaicParams
  ) -> tuple[np.ndarray, np.ndarray]:
    """Validación: ejecuta las etapas 1 y 2 y devuelve ``tile_desc`` y ``cell_desc``, sin medir."""
    if self.init_ms is None:
      self.warmup()
    with self._active():
      choice = np.zeros(target_src.shape[0] // CELL_PX * params.cols, dtype=np.int32)
      job = MosaicJob.create(tiles_src, target_src, params, choice)
      try:
        return self._descriptors_of(job)
      finally:
        self._release(job)

  def _descriptors_of(self, job: MosaicJob) -> tuple[np.ndarray, np.ndarray]:
    """Sube las entradas, calcula los descriptores y los lee del dispositivo."""
    self._upload(job, self._create_timer())
    self._prepare_tiles(job, lambda fraction: None)
    self._target_descriptors(job, lambda fraction: None)
    tile_desc = self._read(job.buffers["tile_desc"], (job.n_tiles, DESC_DIM), np.float32)
    return tile_desc, self._read(job.buffers["cell_desc"], (job.n_cells, DESC_DIM), np.float32)

  # --- Pasos del Template Method -------------------------------------------------------

  def _warmup(self) -> None:
    """Compila los kernels y ejecuta un trabajo sintético mínimo (primer lanzamiento)."""
    self._build_kernels()
    job = MosaicJob.warmup()
    try:
      self._execute(job, self._create_progress(None))
    finally:
      self._release(job)

  def _create_progress(self, on_progress: ProgressCallback | None) -> ProgressReporter:
    """El progreso se difiere hasta que el dispositivo alcanza cada marcador."""
    self._progress = DeferredProgressReporter(on_progress, self._record_marker, self._wait_marker)
    return self._progress

  def _execute(self, job: MosaicJob, progress: ProgressReporter) -> MosaicResult:
    """Ejecuta el trabajo traduciendo los errores de memoria del driver."""
    try:
      return super()._execute(job, progress)
    except Exception as error:
      if self._is_out_of_memory(error):
        raise OutOfMemoryError(f"{OUT_OF_MEMORY_MESSAGE} para el trabajo en {self.name}") from error
      raise

  def _upload(self, job: MosaicJob, timer: StageTimer) -> None:
    """Reserva todos los buffers, calcula el bloque del matching y copia las entradas (D4)."""
    for name, nbytes in job_buffer_sizes(job).items():
      job.buffers[name] = self._alloc(nbytes)
    self._m_chunk = self._chunk_rows(job)
    job.buffers[DIST_BUFFER] = self._alloc(self._m_chunk * job.n_tiles * FLOAT32_BYTES)
    self._copy_inputs(job, timer)

  def _chunk_rows(self, job: MosaicJob) -> int:
    """Bloque forzado (acotado por M) o calculado según la memoria del dispositivo."""
    if self.chunk_cells is not None:
      return min(self.chunk_cells, job.n_cells)
    return matching_chunk_rows(self._available_matching_bytes(job), job.n_tiles, job.n_cells, self._max_alloc_bytes())

  def _prepare_tiles(self, job: MosaicJob, report: StepProgress) -> None:
    """Etapa 1: resize_tiles, tile_descriptors y sq_norms de las teselas."""
    buffers, n_tiles, tile_px = job.buffers, job.n_tiles, job.params.tile_px
    n = int_arg(n_tiles)
    self._launch_1d(
      "resize_tiles", n_tiles * tile_px * tile_px, buffers["tiles_src"], buffers["tiles_px"], n, int_arg(tile_px)
    )
    self._launch_1d("tile_descriptors", n_tiles * DESC_GRID * DESC_GRID, buffers["tiles_src"], buffers["tile_desc"], n)
    self._launch_1d("sq_norms", n_tiles, buffers["tile_desc"], buffers["tile_norms"], n)

  def _target_descriptors(self, job: MosaicJob, report: StepProgress) -> None:
    """Etapa 2: cell_descriptors y sq_norms de las celdas."""
    buffers = job.buffers
    grid_args = (int_arg(job.rows), int_arg(job.cols))
    self._launch_1d(
      "cell_descriptors", job.n_cells * CELL_PX * CELL_PX, buffers["target_src"], buffers["cell_desc"], *grid_args
    )
    self._launch_1d("sq_norms", job.n_cells, buffers["cell_desc"], buffers["cell_norms"], int_arg(job.n_cells))

  def _match(self, job: MosaicJob, report: StepProgress) -> None:
    """Etapa 3: distances_tiled y topk_rows por bloques, todo encolado sin esperar (D4)."""
    for row_offset in range(0, job.n_cells, self._m_chunk):
      rows = min(self._m_chunk, job.n_cells - row_offset)
      self._launch_distances(job, row_offset, rows)
      self._launch_topk(job, row_offset, rows)
      report((row_offset + rows) / job.n_cells)

  def _launch_distances(self, job: MosaicJob, row_offset: int, rows: int) -> None:
    """Un bloque 16×16 por tile de 16 celdas × 16 teselas de la matriz del chunk."""
    b = job.buffers
    grid = (ceil_div(job.n_tiles, MATMUL_TILE), ceil_div(rows, MATMUL_TILE))
    args = (b["cell_desc"], b["tile_desc"], b["cell_norms"], b["tile_norms"], b[DIST_BUFFER])
    self._launch(
      "distances_tiled",
      grid,
      (MATMUL_TILE, MATMUL_TILE),
      (*args, int_arg(row_offset), int_arg(rows), int_arg(job.n_tiles)),
    )

  def _launch_topk(self, job: MosaicJob, row_offset: int, rows: int) -> None:
    """Un bloque de TOPK_THREADS hilos por fila del chunk."""
    b = job.buffers
    scalars = (int_arg(row_offset), int_arg(rows), int_arg(job.n_tiles), int_arg(job.params.k))
    self._launch("topk_rows", (rows,), (TOPK_THREADS,), (b[DIST_BUFFER], b["topk_idx"], b["topk_dist"], *scalars))

  def _compose(self, job: MosaicJob, report: StepProgress) -> None:
    """Etapa 4: compose, un hilo por píxel de la imagen final."""
    b, (height, width, _) = job.buffers, job.output_shape
    grid = (ceil_div(width, COMPOSE_TILE), ceil_div(height, COMPOSE_TILE))
    tensors = (b["tiles_px"], b["target_src"], b["topk_idx"], b["choice"], b["image"])
    scalars = (
      int_arg(job.rows),
      int_arg(job.cols),
      int_arg(job.params.tile_px),
      int_arg(job.params.k),
      np.float32(job.params.alpha),
    )
    self._launch("compose", grid, (COMPOSE_TILE, COMPOSE_TILE), (*tensors, *scalars))

  def _download(self, job: MosaicJob, timer: GpuStageTimer) -> np.ndarray:
    """Encola la copia de la imagen, reenvía el progreso a medida que avanza y sincroniza (D4)."""
    staging_start = time.perf_counter()
    staging = self._output_staging(job)
    staging_ms = elapsed_ms_since(staging_start)
    self._enqueue_image_copy(job, staging, timer)
    self._progress.drain()
    self._synchronize()
    copy_start = time.perf_counter()
    image = self._read_staging(staging, job.output_shape)
    timer.record_host(Stage.STAGING_D2H, staging_ms + elapsed_ms_since(copy_start))
    return image

  def _collect_topk(self, job: MosaicJob) -> tuple[np.ndarray, np.ndarray]:
    """Copia ``topk_idx`` y ``topk_dist`` al host, ya fuera de la medición."""
    shape = (job.n_cells, job.params.k)
    return self._read(job.buffers["topk_idx"], shape, np.int32), self._read(job.buffers["topk_dist"], shape, np.float32)

  def _release(self, job: MosaicJob) -> None:
    """Espera lo pendiente y libera los buffers del trabajo, también si falló."""
    try:
      self._synchronize()
    finally:
      for buffer in job.buffers.values():
        self._free(buffer)
      job.buffers.clear()

  def _launch_1d(self, name: str, n_threads: int, *args: Any) -> None:
    """Lanza un kernel 1D con bloques de BLOCK_1D hilos."""
    self._launch(name, (ceil_div(n_threads, BLOCK_1D),), (BLOCK_1D,), args)

  # --- Primitivas de cada API -------------------------------------------------------------

  def _active(self) -> AbstractContextManager:
    """Contexto en el que la GPU queda activa para el hilo actual (por defecto, nada)."""
    return nullcontext()

  @abstractmethod
  def _build_kernels(self) -> None:
    """Compila kernels/mosaic.* con los -D de ``kernel_build``."""

  @abstractmethod
  def _alloc(self, nbytes: int) -> Any:
    """Reserva un buffer del dispositivo."""

  @abstractmethod
  def _free(self, buffer: Any) -> None:
    """Libera un buffer del dispositivo."""

  @abstractmethod
  def _available_matching_bytes(self, job: MosaicJob) -> int:
    """Bytes disponibles para la matriz de distancias después de reservar lo demás."""

  def _max_alloc_bytes(self) -> int | None:
    """Tamaño máximo de una reserva individual, si el dispositivo lo limita."""
    return None

  @abstractmethod
  def _copy_inputs(self, job: MosaicJob, timer: GpuStageTimer) -> None:
    """Copia tiles_src, target_src y choice al dispositivo a través del staging."""

  @abstractmethod
  def _launch(self, name: str, grid: Grid, block: Grid, args: tuple) -> None:
    """Encola un kernel: ``grid`` en bloques y ``block`` en hilos, como en CUDA."""

  @abstractmethod
  def _output_staging(self, job: MosaicJob) -> Any:
    """Staging de host (reutilizable) para la imagen final."""

  @abstractmethod
  def _enqueue_image_copy(self, job: MosaicJob, staging: Any, timer: StageTimer) -> None:
    """Encola la copia device → staging de la imagen, medida como TRANSFER_D2H."""

  @abstractmethod
  def _read_staging(self, staging: Any, shape: tuple[int, ...]) -> np.ndarray:
    """Copia la imagen del staging a un array nuevo del host."""

  @abstractmethod
  def _read(self, buffer: Any, shape: tuple[int, ...], dtype: type) -> np.ndarray:
    """Copia un buffer del dispositivo al host (fuera de la medición)."""

  @abstractmethod
  def _record_marker(self) -> Any:
    """Registra un marcador en la cola/stream del trabajo."""

  @abstractmethod
  def _wait_marker(self, marker: Any) -> None:
    """Espera a que el dispositivo alcance un marcador."""

  @abstractmethod
  def _synchronize(self) -> None:
    """Espera a que termine todo lo encolado."""

  @abstractmethod
  def _is_out_of_memory(self, error: Exception) -> bool:
    """Indica si ``error`` es una falta de memoria del driver."""

  @abstractmethod
  def close(self) -> None:
    """Libera el contexto y los recursos del dispositivo."""
