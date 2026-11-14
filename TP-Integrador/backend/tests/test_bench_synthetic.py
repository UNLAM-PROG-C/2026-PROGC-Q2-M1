import numpy as np
import pytest

from app.backends.cpu import stages
from app.bench.synthetic import grid_shape, synthetic_target, synthetic_tiles
from app.core.choice import generate_choice
from app.core.constants import CELL_PX, DESC_DIM, MAX_COLS, RGB_CHANNELS, TILE_SRC_PX
from app.core.params import MosaicParams

SEED = 0
OTHER_SEED = 1
# Decimales con los que se comparan descriptores para contarlos como distintos.
DESCRIPTOR_DECIMALS = 3


@pytest.mark.parametrize(("m_cells", "expected"), [(1_000, (25, 40)), (10_000, (80, 125)), (40_000, (160, 250))])
def test_grid_shape_is_close_to_four_thirds(m_cells, expected):
  rows, cols = grid_shape(m_cells)
  assert (rows, cols) == expected
  assert rows * cols == m_cells


def test_grid_shape_respects_max_cols():
  rows, cols = grid_shape(1_000_000)  # la más cercana a 4:3 tendría más de 400 columnas
  assert rows * cols == 1_000_000 and cols <= MAX_COLS


def test_prime_m_gives_a_single_column():
  assert grid_shape(401) == (401, 1)


def test_same_seed_gives_identical_arrays():
  assert np.array_equal(synthetic_tiles(30, SEED), synthetic_tiles(30, SEED))
  assert np.array_equal(synthetic_target(5, 7, SEED), synthetic_target(5, 7, SEED))
  assert not np.array_equal(synthetic_tiles(30, SEED), synthetic_tiles(30, OTHER_SEED))


def test_shapes_and_types():
  tiles, target = synthetic_tiles(3, SEED), synthetic_target(4, 6, SEED)
  assert tiles.shape == (3, TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS) and tiles.dtype == np.uint8
  assert target.shape == (4 * CELL_PX, 6 * CELL_PX, RGB_CHANNELS) and target.dtype == np.uint8


def test_tiles_are_generated_by_chunks_without_seams():
  # Más teselas que un bloque: las primeras coinciden con las de un lote más chico.
  assert np.array_equal(synthetic_tiles(300, SEED)[:256], synthetic_tiles(256, SEED))


def test_hundred_tiles_have_at_least_ninety_distinct_descriptors():
  tiles = synthetic_tiles(100, SEED)
  desc = np.empty((len(tiles), DESC_DIM), dtype=np.float32)
  stages.tile_descriptors(tiles, desc)
  assert len(np.unique(np.round(desc, DESCRIPTOR_DECIMALS), axis=0)) >= 90


def test_same_seed_gives_same_topk(cpu_backend):
  rows, cols = grid_shape(48)
  params = MosaicParams(cols=cols, k=3)
  choice = generate_choice(params.seed, params.k, rows * cols)

  def topk():
    return cpu_backend.run(synthetic_tiles(20, SEED), synthetic_target(rows, cols, SEED), params, choice).topk_idx

  assert np.array_equal(topk(), topk())
