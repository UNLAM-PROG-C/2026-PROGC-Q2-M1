"""Equivalencia CPU vs CUDA vs OpenCL (design D8 del cambio 2).

Se parametriza con los backends GPU que detecta el registro; los no disponibles
se saltean con el motivo (por ejemplo, "biblioteca no instalada"). La referencia
es el backend CPU y la tolerancia es la del cambio 1 (design D3):
- descriptores con ``EQUIVALENCE_LAB_TOLERANCE``;
- ``topk_idx`` igual en al menos ``MIN_MATCHING_CELLS_RATIO`` de las celdas, y
  ``topk_dist`` con ``EQUIVALENCE_DIST_RELATIVE_TOLERANCE`` en esas celdas;
- imagen con a lo sumo ``IMAGE_LEVEL_TOLERANCE`` niveles de diferencia por canal
  en las celdas cuya tesela elegida coincide.
"""

from dataclasses import dataclass

import numpy as np
import pytest

from app.backends.cpu import stages
from app.backends.registry import CUDA, OPENCL
from app.core.choice import generate_choice
from app.core.constants import (
  DESC_BLOCK_PX,
  DESC_DIM,
  EQUIVALENCE_DIST_RELATIVE_TOLERANCE,
  EQUIVALENCE_LAB_TOLERANCE,
  MIN_MATCHING_CELLS_RATIO,
)
from app.core.params import MosaicParams
from tests.conftest import blocky_tiles, random_target, require_backend

GPU_BACKENDS = (CUDA, OPENCL)
# La mezcla α se redondea en float32: FMA puede mover un valor justo en .5.
IMAGE_LEVEL_TOLERANCE = 1
FORCED_CHUNK_CELLS = 16
DUPLICATE_COPIES = 3


@dataclass(frozen=True)
class Case:
  """Un trabajo sintético de la matriz de casos de design D8."""

  name: str
  n_tiles: int
  rows: int
  cols: int
  tile_px: int = 32
  k: int = 5
  alpha: float = 1.0
  chunk_cells: int | None = None
  duplicated: bool = False

  def inputs(self) -> tuple[np.ndarray, np.ndarray, MosaicParams, np.ndarray]:
    tiles = blocky_tiles(self.n_tiles)
    if self.duplicated:
      tiles = np.concatenate([tiles] * DUPLICATE_COPIES)
    params = MosaicParams(cols=self.cols, tile_px=self.tile_px, k=self.k, alpha=self.alpha, seed=self.n_tiles)
    choice = generate_choice(params.seed, params.k, self.rows * self.cols)
    return tiles, random_target(self.rows, self.cols), params, choice


CASES = (
  Case("n_y_m_no_multiplos_de_16", n_tiles=37, rows=5, cols=7),
  Case("n_menor_que_128_con_k_16", n_tiles=20, rows=6, cols=9, k=16),
  Case("teselas_duplicadas_empates", n_tiles=11, rows=4, cols=6, k=5, duplicated=True),
  Case("tile_px_16_k_1_alpha_medio", n_tiles=40, rows=7, cols=10, tile_px=16, k=1, alpha=0.5),
  Case("tile_px_64_alpha_cero", n_tiles=33, rows=3, cols=5, tile_px=64, alpha=0.0),
  Case("mediano_n_mayor_que_128", n_tiles=300, rows=23, cols=41, k=16, alpha=0.5),
  Case("bloque_de_matching_forzado", n_tiles=150, rows=9, cols=13, chunk_cells=FORCED_CHUNK_CELLS),
)


def chosen_tiles_match(gpu_result, cpu_result, choice: np.ndarray) -> np.ndarray:
  cells = np.arange(choice.shape[0])
  return gpu_result.topk_idx[cells, choice] == cpu_result.topk_idx[cells, choice]


def assert_images_equivalent(gpu_result, cpu_result, case: Case, choice: np.ndarray) -> None:
  same_cell = chosen_tiles_match(gpu_result, cpu_result, choice).reshape(case.rows, case.cols)
  same_pixel = np.repeat(np.repeat(same_cell, case.tile_px, axis=0), case.tile_px, axis=1)
  diff = np.abs(gpu_result.image.astype(np.int16) - cpu_result.image.astype(np.int16)).max(axis=2)
  assert gpu_result.image.shape == cpu_result.image.shape
  assert diff[same_pixel].max() <= IMAGE_LEVEL_TOLERANCE


def assert_topk_equivalent(gpu_result, cpu_result) -> None:
  same_rows = np.all(gpu_result.topk_idx == cpu_result.topk_idx, axis=1)
  assert same_rows.mean() >= MIN_MATCHING_CELLS_RATIO
  np.testing.assert_allclose(
    gpu_result.topk_dist[same_rows], cpu_result.topk_dist[same_rows], rtol=EQUIVALENCE_DIST_RELATIVE_TOLERANCE
  )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
@pytest.mark.parametrize("backend_name", GPU_BACKENDS)
def test_gpu_backend_matches_cpu(backend_registry, cpu_backend, monkeypatch, backend_name, case):
  backend = require_backend(backend_registry, backend_name)
  monkeypatch.setattr(backend, "chunk_cells", case.chunk_cells)
  tiles, target, params, choice = case.inputs()
  gpu_result = backend.run(tiles, target, params, choice)
  cpu_result = cpu_backend.run(tiles, target, params, choice)
  assert_topk_equivalent(gpu_result, cpu_result)
  assert_images_equivalent(gpu_result, cpu_result, case, choice)


@pytest.mark.parametrize("backend_name", GPU_BACKENDS)
def test_gpu_descriptors_match_cpu(backend_registry, backend_name):
  backend = require_backend(backend_registry, backend_name)
  tiles, target, params, _ = CASES[0].inputs()
  tile_desc, cell_desc = backend.read_descriptors(tiles, target, params)
  expected_tiles = np.empty((tiles.shape[0], DESC_DIM), dtype=np.float32)
  expected_cells = np.empty((CASES[0].rows * CASES[0].cols, DESC_DIM), dtype=np.float32)
  stages.tile_descriptors(tiles, expected_tiles)
  stages.cell_descriptors(target, params.cols, expected_cells)
  np.testing.assert_allclose(tile_desc, expected_tiles, atol=EQUIVALENCE_LAB_TOLERANCE)
  np.testing.assert_allclose(cell_desc, expected_cells, atol=EQUIVALENCE_LAB_TOLERANCE)


@pytest.mark.parametrize("backend_name", GPU_BACKENDS)
def test_duplicated_tiles_tie_break_by_lowest_index(backend_registry, backend_name):
  backend = require_backend(backend_registry, backend_name)
  case = CASES[2]
  tiles, target, params, choice = case.inputs()
  result = backend.run(tiles, target, params, choice)
  # La tesela i y sus copias i + n, i + 2n están a la misma distancia: deben aparecer en ese orden.
  first = result.topk_idx[:, 0]
  assert np.all(first < case.n_tiles)
  assert np.all(result.topk_idx[:, 1] == first + case.n_tiles)


# Spec kernels-gpu, "empate entre porciones de hilos distintos": con TOPK_THREADS = 128,
# la tesela 5 la recorre el hilo 5 y la 70 el hilo 70; la 133 vuelve a caer en el hilo 5.
TIED_TILES = (5, 70, 133)
TIE_BATCH = 200


@pytest.mark.parametrize("backend_name", GPU_BACKENDS)
def test_tie_across_threads_keeps_index_order(backend_registry, backend_name):
  backend = require_backend(backend_registry, backend_name)
  tiles = blocky_tiles(TIE_BATCH)
  tiles[list(TIED_TILES)] = tiles[TIED_TILES[0]]
  # Una celda cuyo bloque 8×8 es la miniatura de la tesela 5: distancia mínima a 5, 70 y 133.
  target = np.ascontiguousarray(tiles[TIED_TILES[0], ::DESC_BLOCK_PX, ::DESC_BLOCK_PX])
  params = MosaicParams(cols=1, k=len(TIED_TILES))
  result = backend.run(tiles, target, params, np.zeros(1, dtype=np.int32))
  assert tuple(result.topk_idx[0]) == TIED_TILES
