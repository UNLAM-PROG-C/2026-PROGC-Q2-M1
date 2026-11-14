"""Reglas del algoritmo sobre las etapas compiladas del backend CPU."""

import numpy as np
import pytest

from app.backends.cpu import stages
from app.core.color import srgb_to_lab_reference
from app.core.constants import CELL_PX, DESC_BLOCK_PX, DESC_DIM, DESC_GRID, RGB_CHANNELS, TILE_SRC_PX
from tests.conftest import random_target, random_tiles, solid_tiles

# Tolerancia contra la conversión de referencia float64 (task 4.3).
REFERENCE_DESC_TOLERANCE = 1e-3
RED = (255, 0, 0)


def resize(tiles_src: np.ndarray, tile_px: int) -> np.ndarray:
  tiles_px = np.empty((tiles_src.shape[0], tile_px, tile_px, RGB_CHANNELS), dtype=np.uint8)
  stages.resize_tiles(tiles_src, tile_px, tiles_px)
  return tiles_px


def descriptors_of(tiles_src: np.ndarray) -> np.ndarray:
  tile_desc = np.empty((tiles_src.shape[0], DESC_DIM), dtype=np.float32)
  stages.tile_descriptors(tiles_src, tile_desc)
  return tile_desc


def topk_of(dist: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
  topk_idx = np.empty((dist.shape[0], k), dtype=np.int32)
  topk_dist = np.empty((dist.shape[0], k), dtype=np.float32)
  stages.topk_rows(dist, 0, topk_idx, topk_dist)
  return topk_idx, topk_dist


def compose_single_cell(tile_value: int, target_value: int, alpha: float, tile_px: int) -> np.ndarray:
  tiles_px = np.full((1, tile_px, tile_px, RGB_CHANNELS), tile_value, dtype=np.uint8)
  target_src = np.full((CELL_PX, CELL_PX, RGB_CHANNELS), target_value, dtype=np.uint8)
  out = np.empty((tile_px, tile_px, RGB_CHANNELS), dtype=np.uint8)
  topk_idx, choice = np.zeros((1, 1), dtype=np.int32), np.zeros(1, dtype=np.int32)
  stages.compose(tiles_px, target_src, topk_idx, choice, 1, np.float32(alpha), out)
  return out


# --- Redimensionado de teselas ---------------------------------------------------


def test_resize_uniform_block_keeps_color():
  assert np.all(resize(solid_tiles([(10, 20, 30)]), 32) == (10, 20, 30))


def test_resize_rounds_to_nearest():
  tiles_src = np.ones((1, TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS), dtype=np.uint8)
  tiles_src[0, 0, 0, 0] = 0  # El bloque 2×2 de la esquina queda 0, 1, 1, 1.
  assert resize(tiles_src, 64)[0, 0, 0, 0] == 1


# --- Composición -------------------------------------------------------------------


def test_compose_alpha_one_copies_tile_exactly():
  tiles_px = resize(random_tiles(3), 16)
  topk_idx, choice = np.array([[2], [0]], dtype=np.int32), np.zeros(2, dtype=np.int32)
  out = np.empty((16, 32, RGB_CHANNELS), dtype=np.uint8)
  stages.compose(tiles_px, random_target(1, 2), topk_idx, choice, 2, np.float32(1.0), out)
  np.testing.assert_array_equal(out[:, :16], tiles_px[2])
  np.testing.assert_array_equal(out[:, 16:], tiles_px[0])


def test_compose_alpha_zero_is_target_upscaled_by_nearest_neighbor():
  target_src = random_target(1, 1)
  tiles_px = resize(random_tiles(1), 32)
  out = np.empty((32, 32, RGB_CHANNELS), dtype=np.uint8)
  zeros = np.zeros((1, 1), dtype=np.int32)
  stages.compose(tiles_px, target_src, zeros, zeros[0], 1, np.float32(0.0), out)
  np.testing.assert_array_equal(out, np.repeat(np.repeat(target_src, 4, axis=0), 4, axis=1))


def test_compose_alpha_half_mixes():
  assert np.all(compose_single_cell(200, 100, 0.5, 16) == 150)


# --- Descriptores ----------------------------------------------------------------------


def test_tile_descriptors_match_reference_conversion():
  tiles_src = random_tiles(3)
  blocks = tiles_src.reshape(3, DESC_GRID, DESC_BLOCK_PX, DESC_GRID, DESC_BLOCK_PX, RGB_CHANNELS)
  expected = srgb_to_lab_reference(blocks.mean(axis=(2, 4))).reshape(3, DESC_DIM)
  np.testing.assert_allclose(descriptors_of(tiles_src), expected, atol=REFERENCE_DESC_TOLERANCE)


def test_uniform_red_tile_descriptor_is_red_lab_64_times():
  expected = np.tile(srgb_to_lab_reference(np.array(RED)), DESC_GRID * DESC_GRID)
  np.testing.assert_allclose(descriptors_of(solid_tiles([RED]))[0], expected, atol=REFERENCE_DESC_TOLERANCE)


def test_cell_descriptors_follow_row_major_cells():
  rows, cols = 3, 4
  target_src = random_target(rows, cols)
  cell_desc = np.empty((rows * cols, DESC_DIM), dtype=np.float32)
  stages.cell_descriptors(target_src, cols, cell_desc)
  expected_last = srgb_to_lab_reference(target_src[16:24, 24:32]).reshape(DESC_DIM)
  np.testing.assert_allclose(cell_desc[11], expected_last, atol=REFERENCE_DESC_TOLERANCE)


# --- Distancias y top-k ------------------------------------------------------------------


def test_identical_descriptors_have_negligible_distance():
  desc = descriptors_of(random_tiles(1))
  norms = np.empty(1, dtype=np.float32)
  stages.sq_norms(desc, norms)
  dist = np.empty((1, 1), dtype=np.float32)
  stages.distances(desc, desc, norms, norms, 0, dist)
  assert abs(dist[0, 0]) <= norms[0] * np.finfo(np.float32).eps * DESC_DIM


def test_exact_tie_prefers_lower_index():
  dist = np.full((1, 10), 50.0, dtype=np.float32)
  dist[0, [3, 7]] = 1.0
  assert topk_of(dist, 2)[0][0].tolist() == [3, 7]


def test_all_identical_tiles_give_first_indices():
  topk_idx, _ = topk_of(np.full((5, 8), 2.5, dtype=np.float32), 4)
  assert all(row == [0, 1, 2, 3] for row in topk_idx.tolist())


@pytest.mark.parametrize("k", [1, 3])
def test_topk_is_sorted_best_first(k):
  dist = np.array([[9.0, 1.0, 4.0, 2.0]], dtype=np.float32)
  topk_idx, topk_dist = topk_of(dist, k)
  assert topk_idx[0].tolist() == [1, 3, 2][:k]
  assert topk_dist[0].tolist() == [1.0, 2.0, 4.0][:k]


def test_insert_in_the_middle():
  best_dist = np.array([1.0, 4.0, 9.0], dtype=np.float32)
  best_idx = np.array([0, 1, 2], dtype=np.int32)
  stages.insert_sorted(best_dist, best_idx, np.float32(2.0), 5)
  assert best_dist.tolist() == [1.0, 2.0, 4.0]
  assert best_idx.tolist() == [0, 5, 1]
