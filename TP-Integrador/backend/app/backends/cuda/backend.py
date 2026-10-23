"""Backend CUDA con PyCUDA (spec backend-cuda, design D1/D4/D5/D6 del cambio 2).

- PyCUDA se importa **dentro** del constructor: importar este módulo nunca
  falla, aunque no haya PyCUDA ni GPU NVIDIA; el backend se reporta no
  disponible recién al intentar crearlo.
- Contexto explícito (sin ``pycuda.autoinit``) sobre el dispositivo 0. Se crea
  y se desactiva enseguida; cada operación pública lo activa (``push``) y lo
  desactiva (``pop``) al terminar, así nunca queda en la pila de contextos de
  otro código. ``close()`` libera todo y lo destruye (``detach``).
- Un único stream por backend: todas las copias y kernels de un trabajo se
  encolan en él, en orden.
- Staging page-locked (``pagelocked_empty``) reutilizable para las entradas y
  para la imagen; si no se puede reservar, se usa memoria paginable y el
  resultado lo informa.
"""

import atexit
import logging
import time
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import numpy as np

from app.backends.cuda.host_compiler import HostCompilerNotFoundError, extra_nvcc_options, host_compiler_options
from app.backends.cuda.timing import CudaEventTimer
from app.backends.gpu_base import (
  INPUT_NAMES,
  KERNEL_NAMES,
  NOTE_PAGEABLE_TRANSFER,
  REASON_KERNEL_BUILD,
  REASON_NO_CUDA_DEVICES,
  GpuBackend,
  GpuStageTimer,
  pack_inputs,
)
from app.backends.kernel_build import CUDA_SOURCE_NAME, define_options, load_kernel_source
from app.core.backend import BackendInitError
from app.core.constants import GPU_MEMORY_FRACTION
from app.core.job import MosaicJob
from app.core.result import Stage
from app.core.timing import StageTimer, elapsed_ms_since

CUDA_BACKEND_NAME = "cuda"
# Design D7: CUDA usa el dispositivo 0.
CUDA_DEVICE_INDEX = 0
INPUT_STAGING = "input"
OUTPUT_STAGING = "output"

logger = logging.getLogger(__name__)


def _load_driver() -> Any:
  """Importa e inicializa el driver de PyCUDA (``ImportError`` si no está instalado)."""
  import pycuda.driver as drv  # Import diferido: ver docstring del módulo.

  drv.init()
  return drv


class CudaBackend(GpuBackend):
  """Fotomosaico en una GPU NVIDIA con kernels CUDA propios."""

  name = CUDA_BACKEND_NAME

  def __init__(self, chunk_cells: int | None = None) -> None:
    """Crea el contexto en el dispositivo 0; falla si no hay dispositivos CUDA."""
    drv = _load_driver()
    if drv.Device.count() == 0:
      raise BackendInitError(REASON_NO_CUDA_DEVICES)
    device = drv.Device(CUDA_DEVICE_INDEX)
    super().__init__(device.name(), chunk_cells)
    self._drv = drv
    self._context = device.make_context()
    self._context.pop()
    self._stream: Any = None
    self._kernels: dict[str, Any] = {}
    self._staging: dict[str, np.ndarray] = {}
    self._timer: CudaEventTimer | None = None
    atexit.register(self.close)

  @contextmanager
  def _active(self) -> Iterator[None]:
    """Activa el contexto CUDA en el hilo actual mientras dura la operación."""
    if self._context is None:
      raise RuntimeError("el backend CUDA ya está cerrado")
    self._context.push()
    try:
      yield
    finally:
      self._context.pop()

  def close(self) -> None:
    """Libera staging, módulo y stream, y destruye el contexto (idempotente)."""
    if self._context is None:
      return
    with self._active():
      for staging in self._staging.values():
        staging.base.free()
      self._staging, self._kernels, self._stream = {}, {}, None
    self._context.detach()
    self._context = None

  # --- Compilación -----------------------------------------------------------------

  def _build_kernels(self) -> None:
    """Compila mosaic.cu con los -D compartidos y crea el stream del backend."""
    from pycuda.compiler import SourceModule  # Import diferido.

    try:
      options = [*define_options(), *host_compiler_options(), *extra_nvcc_options()]
      with warnings.catch_warnings(record=True) as compiler_output:
        module = SourceModule(load_kernel_source(CUDA_SOURCE_NAME), no_extern_c=True, options=options)
    except (self._drv.CompileError, HostCompilerNotFoundError) as error:
      raise BackendInitError(REASON_KERNEL_BUILD, str(error)) from error
    for message in compiler_output:
      logger.debug("salida de nvcc: %s", message.message)
    self._kernels = {name: module.get_function(name) for name in KERNEL_NAMES}
    self._stream = self._drv.Stream()

  # --- Memoria y transferencias ---------------------------------------------------------

  def _create_timer(self) -> StageTimer:
    """Eventos CUDA en el stream del trabajo."""
    self._timer = CudaEventTimer(self._stream, self._drv.Event)
    return self._timer

  def _alloc(self, nbytes: int) -> Any:
    """Reserva memoria global del dispositivo (al menos 1 byte)."""
    return self._drv.mem_alloc(max(nbytes, 1))

  def _free(self, buffer: Any) -> None:
    """Libera un buffer del dispositivo."""
    buffer.free()

  def _available_matching_bytes(self, job: MosaicJob) -> int:
    """Fracción configurada de la memoria libre, medida después de reservar lo demás."""
    free_bytes, _ = self._drv.mem_get_info()
    return int(free_bytes * GPU_MEMORY_FRACTION)

  def _staging_bytes(self, key: str, nbytes: int, job: MosaicJob) -> np.ndarray:
    """Staging page-locked reutilizable; si no se puede reservar, memoria paginable."""
    current = self._staging.get(key)
    if current is not None and current.nbytes >= nbytes:
      return current[:nbytes]
    if current is not None:
      current.base.free()
      del self._staging[key]
    try:
      self._staging[key] = self._drv.pagelocked_empty(nbytes, np.uint8)
    except (self._drv.Error, MemoryError):
      job.notes.append(NOTE_PAGEABLE_TRANSFER)
      return np.empty(nbytes, dtype=np.uint8)
    return self._staging[key]

  def _copy_inputs(self, job: MosaicJob, timer: GpuStageTimer) -> None:
    """Copia a staging (reloj de pared) y encola los H→D (eventos) en el stream."""
    start = time.perf_counter()
    staging = self._staging_bytes(INPUT_STAGING, sum(getattr(job, name).nbytes for name in INPUT_NAMES), job)
    placed = list(pack_inputs(staging, job))
    timer.record_host(Stage.STAGING_H2D, elapsed_ms_since(start))
    timer.start(Stage.TRANSFER_H2D)
    for name, offset, nbytes in placed:
      self._drv.memcpy_htod_async(job.buffers[name], staging[offset : offset + nbytes], self._stream)
    timer.stop(Stage.TRANSFER_H2D)

  def _output_staging(self, job: MosaicJob) -> np.ndarray:
    """Staging para la imagen final."""
    return self._staging_bytes(OUTPUT_STAGING, int(np.prod(job.output_shape)), job)

  def _enqueue_image_copy(self, job: MosaicJob, staging: np.ndarray, timer: StageTimer) -> None:
    """Única copia D→H medida del trabajo: la imagen final."""
    timer.start(Stage.TRANSFER_D2H)
    self._drv.memcpy_dtoh_async(staging, job.buffers["image"], self._stream)
    timer.stop(Stage.TRANSFER_D2H)

  def _read_staging(self, staging: np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    """Copia la imagen del staging (que se reutiliza) a un array propio."""
    return staging.reshape(shape).copy()

  def _read(self, buffer: Any, shape: tuple[int, ...], dtype: type) -> np.ndarray:
    """Copia de validación en el mismo stream, después de la medición."""
    out = np.empty(shape, dtype=dtype)
    self._drv.memcpy_dtoh_async(out, buffer, self._stream)
    self._stream.synchronize()
    return out

  # --- Lanzamientos y sincronización ------------------------------------------------------

  def _launch(self, name: str, grid: tuple[int, ...], block: tuple[int, ...], args: tuple) -> None:
    """Encola un kernel en el stream del trabajo (grilla y bloque completados a 3D)."""
    self._kernels[name](*args, grid=_dim3(grid), block=_dim3(block), stream=self._stream)

  def _record_marker(self) -> Any:
    """Evento CUDA registrado en el stream (para el progreso diferido)."""
    event = self._drv.Event()
    event.record(self._stream)
    return event

  def _wait_marker(self, marker: Any) -> None:
    """Espera a que el stream alcance el evento."""
    marker.synchronize()

  def _synchronize(self) -> None:
    """Espera a que termine todo lo encolado en el stream."""
    if self._stream is not None:
      self._stream.synchronize()

  def _is_out_of_memory(self, error: Exception) -> bool:
    """Falta de memoria del dispositivo informada por el driver."""
    return isinstance(error, self._drv.MemoryError)


def _dim3(sizes: tuple[int, ...]) -> tuple[int, int, int]:
  """Completa una grilla o bloque de 1 o 2 dimensiones a las 3 que pide CUDA."""
  return (*sizes, *(1,) * (3 - len(sizes)))
