"""Backend CPU secuencial: implementación de referencia, siempre disponible.

Implementa los pasos de ``BaseBackend`` (Template Method) llamando a las
funciones compiladas de ``stages.py``. El bucle de bloques del matching está en
Python y llama a funciones compiladas por bloque: así se informa el progreso
entre bloques sin volver al intérprete dentro de una etapa.
"""

import platform

import numpy as np

from app.backends.cpu import stages
from app.core.backend import BaseBackend, StepProgress
from app.core.constants import (
  CELL_PX,
  CPU_DISTANCE_BUDGET_BYTES,
  DESC_DIM,
  FLOAT32_BYTES,
  MIN_K,
  RGB_CHANNELS,
  TILE_SRC_PX,
)
from app.core.job import MosaicJob
from app.core.params import MosaicParams
from app.core.timing import PerfCounterTimer, StageTimer

CPU_BACKEND_NAME = "cpu"
FALLBACK_DEVICE_NAME = "CPU"
# Trabajo mínimo del warmup: dos teselas y una grilla de 1×2 celdas.
WARMUP_TILES = 2
WARMUP_COLS = 2


def chunk_cells_for_budget(n_tiles: int, budget_bytes: int) -> int:
  """Celdas por bloque para que ``[m_chunk, N]`` float32 no supere el presupuesto."""
  return max(1, budget_bytes // (n_tiles * FLOAT32_BYTES))


class CpuBackend(BaseBackend):
  """Fotomosaico secuencial en un solo hilo, compilado con Numba."""

  name = CPU_BACKEND_NAME

  def __init__(self, distance_budget_bytes: int = CPU_DISTANCE_BUDGET_BYTES, chunk_cells: int | None = None) -> None:
    """Configura el presupuesto del matching; ``chunk_cells`` fuerza un tamaño de bloque."""
    super().__init__(platform.processor() or FALLBACK_DEVICE_NAME)
    self.distance_budget_bytes = distance_budget_bytes
    self.chunk_cells = chunk_cells

  def _warmup(self) -> None:
    """Compila todas las etapas ejecutando un trabajo mínimo con los mismos tipos."""
    tiles_src = np.zeros((WARMUP_TILES, TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS), dtype=np.uint8)
    target_src = np.zeros((CELL_PX, WARMUP_COLS * CELL_PX, RGB_CHANNELS), dtype=np.uint8)
    params = MosaicParams(cols=WARMUP_COLS, k=MIN_K)
    job = MosaicJob.create(tiles_src, target_src, params, np.zeros(WARMUP_COLS, dtype=np.int32))
    for _, step in self._compute_steps():
      step(job, lambda fraction: None)

  def _create_timer(self) -> StageTimer:
    """En CPU se mide con ``time.perf_counter``."""
    return PerfCounterTimer()

  def _prepare_tiles(self, job: MosaicJob, report: StepProgress) -> None:
    """Etapa 1: resize_tiles, tile_descriptors y normas de las teselas."""
    tile_px = job.params.tile_px
    tiles_px = np.empty((job.n_tiles, tile_px, tile_px, RGB_CHANNELS), dtype=np.uint8)
    tile_desc = np.empty((job.n_tiles, DESC_DIM), dtype=np.float32)
    tile_norms = np.empty(job.n_tiles, dtype=np.float32)
    stages.resize_tiles(job.tiles_src, tile_px, tiles_px)
    stages.tile_descriptors(job.tiles_src, tile_desc)
    stages.sq_norms(tile_desc, tile_norms)
    job.buffers.update(tiles_px=tiles_px, tile_desc=tile_desc, tile_norms=tile_norms)

  def _target_descriptors(self, job: MosaicJob, report: StepProgress) -> None:
    """Etapa 2: cell_descriptors y normas de las celdas."""
    cell_desc = np.empty((job.n_cells, DESC_DIM), dtype=np.float32)
    cell_norms = np.empty(job.n_cells, dtype=np.float32)
    stages.cell_descriptors(job.target_src, job.cols, cell_desc)
    stages.sq_norms(cell_desc, cell_norms)
    job.buffers.update(cell_desc=cell_desc, cell_norms=cell_norms)

  def _match(self, job: MosaicJob, report: StepProgress) -> None:
    """Etapa 3: distancias y top-k por bloques de celdas, sin fusionarlos (como en GPU)."""
    chunk = min(job.n_cells, self.chunk_cells or chunk_cells_for_budget(job.n_tiles, self.distance_budget_bytes))
    dist = np.empty((chunk, job.n_tiles), dtype=np.float32)
    topk_idx = np.empty((job.n_cells, job.params.k), dtype=np.int32)
    topk_dist = np.empty((job.n_cells, job.params.k), dtype=np.float32)
    buffers = job.buffers
    for row_offset in range(0, job.n_cells, chunk):
      block = dist[: min(chunk, job.n_cells - row_offset)]
      stages.distances(
        buffers["cell_desc"], buffers["tile_desc"], buffers["cell_norms"], buffers["tile_norms"], row_offset, block
      )
      stages.topk_rows(block, row_offset, topk_idx, topk_dist)
      report((row_offset + block.shape[0]) / job.n_cells)
    job.buffers.update(topk_idx=topk_idx, topk_dist=topk_dist)

  def _compose(self, job: MosaicJob, report: StepProgress) -> None:
    """Etapa 4: compose."""
    image = np.empty(job.output_shape, dtype=np.uint8)
    alpha = np.float32(job.params.alpha)
    stages.compose(job.buffers["tiles_px"], job.target_src, job.buffers["topk_idx"], job.choice, job.cols, alpha, image)
    job.buffers["image"] = image

  def _download(self, job: MosaicJob, timer: StageTimer) -> np.ndarray:
    """En CPU la imagen ya está en memoria del host: no hay transferencias."""
    return job.buffers["image"]

  def _collect_topk(self, job: MosaicJob) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve el top-k calculado."""
    return job.buffers["topk_idx"], job.buffers["topk_dist"]
