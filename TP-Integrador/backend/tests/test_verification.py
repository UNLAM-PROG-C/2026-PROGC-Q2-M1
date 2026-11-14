import numpy as np
import pytest

from app.core.constants import RGB_CHANNELS
from app.core.verification import FingerprintMismatchError, fingerprint, verify

ROWS, COLS, TILE_PX, K = 3, 4, 8, 5
SEED = 7


def random_result(seed: int = SEED) -> tuple[np.ndarray, np.ndarray]:
  rng = np.random.default_rng(seed)
  image = rng.integers(0, 256, (ROWS * TILE_PX, COLS * TILE_PX, RGB_CHANNELS), dtype=np.uint8)
  topk_idx = rng.integers(0, 100, (ROWS * COLS, K), dtype=np.int32)
  return image, topk_idx


def verify_pair(cpu: tuple[np.ndarray, np.ndarray], gpu: tuple[np.ndarray, np.ndarray]):
  prints = {"cpu": fingerprint(*cpu, TILE_PX), "cuda": fingerprint(*gpu, TILE_PX)}
  return verify(prints, "cpu")


def test_identical_results_have_no_different_cells():
  summary = verify_pair(random_result(), random_result())
  assert summary.reference == "cpu" and summary.identical
  assert summary.differences["cuda"].total_cells == 0


def test_altered_topk_row_counts_one_cell():
  image, topk_idx = random_result()
  altered = topk_idx.copy()
  altered[5, 2] += 1
  diff = verify_pair((image, topk_idx), (image, altered)).differences["cuda"]
  assert (diff.topk_cells, diff.image_cells, diff.total_cells) == (1, 0, 1)


def test_altered_pixel_counts_one_cell():
  image, topk_idx = random_result()
  altered = image.copy()
  altered[TILE_PX + 3, 2 * TILE_PX + 1, 0] ^= 1
  diff = verify_pair((image, topk_idx), (altered, topk_idx)).differences["cuda"]
  assert (diff.topk_cells, diff.image_cells, diff.total_cells) == (0, 1, 1)


def test_topk_and_pixel_in_same_cell_count_once():
  image, topk_idx = random_result()
  altered_image, altered_topk = image.copy(), topk_idx.copy()
  altered_image[TILE_PX + 3, 2 * TILE_PX + 1, 0] ^= 1  # celda (1, 2) = índice 6
  altered_topk[1 * COLS + 2, 0] += 1
  summary = verify_pair((image, topk_idx), (altered_image, altered_topk))
  diff = summary.differences["cuda"]
  assert (diff.topk_cells, diff.image_cells, diff.total_cells) == (1, 1, 1)
  assert not summary.identical


def test_digests_follow_row_major_cell_order():
  image, topk_idx = random_result()
  altered = image.copy()
  altered[2 * TILE_PX, 3 * TILE_PX, 1] ^= 1  # celda (2, 3)
  original, changed = fingerprint(image, topk_idx, TILE_PX), fingerprint(altered, topk_idx, TILE_PX)
  assert np.flatnonzero(original.cell_digests != changed.cell_digests).tolist() == [2 * COLS + 3]


def test_mismatched_grids_are_rejected():
  image, topk_idx = random_result()
  with pytest.raises(FingerprintMismatchError):
    verify_pair((image, topk_idx), (image, topk_idx[:, :2]))
