"""Etapa común de carga: normalización, pool de decodificación, objetivo y cache."""

import numpy as np
import pytest
from PIL import Image

from app.core.constants import CELL_PX, RGB_CHANNELS, TILE_SRC_PX
from app.loading.cache import LoadCache
from app.loading.decode import decode_tile
from app.loading.target_loader import load_target
from app.loading.tile_loader import NoValidTilesError, TileLoader
from tests.conftest import write_random_images

EXIF_ORIENTATION_TAG = 0x0112
ROTATED_90_CW = 6
RED, GREEN, BLUE = (255, 0, 0), (0, 255, 0), (0, 0, 255)
# Margen para colores después de compresión JPEG.
JPEG_MARGIN = 40
BATCH_NAMES = ["b.png", "a.png", "sub/c.png", "d.webp", "e.jpg", "a2.png", "z/y.png"]


@pytest.fixture(scope="module")
def loader_one():
  with TileLoader(workers=1) as loader:
    yield loader


@pytest.fixture(scope="module")
def loader_four():
  with TileLoader(workers=4) as loader:
    yield loader


def save(pixels: np.ndarray, path, **kwargs) -> None:
  Image.fromarray(pixels).save(path, **kwargs)


# --- Normalización ----------------------------------------------------------------


def test_landscape_takes_central_square(tmp_path):
  pixels = np.zeros((200, 400, RGB_CHANNELS), dtype=np.uint8)
  pixels[:, :100], pixels[:, 100:300], pixels[:, 300:] = RED, GREEN, BLUE
  save(pixels, tmp_path / "wide.png")
  tile = decode_tile(tmp_path / "wide.png")
  assert tile.shape == (TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS) and tile.dtype == np.uint8
  assert np.all(tile == GREEN)


def test_exif_orientation_is_applied(tmp_path):
  pixels = np.zeros((20, 40, RGB_CHANNELS), dtype=np.uint8)
  pixels[:, :20], pixels[:, 20:] = RED, BLUE  # Izquierda roja, derecha azul.
  exif = Image.Exif()
  exif[EXIF_ORIENTATION_TAG] = ROTATED_90_CW
  save(pixels, tmp_path / "rotated.jpg", exif=exif, quality=95)
  tile = decode_tile(tmp_path / "rotated.jpg").astype(int)
  # Rotada 90° en sentido horario: la izquierda queda arriba.
  top, bottom = tile[TILE_SRC_PX // 4, TILE_SRC_PX // 2], tile[3 * TILE_SRC_PX // 4, TILE_SRC_PX // 2]
  assert top[0] > top[2] + JPEG_MARGIN and bottom[2] > bottom[0] + JPEG_MARGIN


@pytest.mark.parametrize("mode", ["RGBA", "L"])
def test_alpha_and_grayscale_become_rgb(tmp_path, mode):
  Image.new(mode, (30, 50)).save(tmp_path / "image.png")
  assert decode_tile(tmp_path / "image.png").shape == (TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS)


# --- Pool de decodificación ------------------------------------------------------


def test_one_and_four_processes_give_identical_bytes(tmp_path, loader_one, loader_four):
  write_random_images(tmp_path, BATCH_NAMES)
  one, four = loader_one.load(tmp_path), loader_four.load(tmp_path)
  assert one.tiles_src.tobytes() == four.tiles_src.tobytes()
  assert one.paths == four.paths == tuple(sorted(BATCH_NAMES))
  np.testing.assert_array_equal(one.tiles_src[0], decode_tile(tmp_path / "a.png"))


def test_corrupt_file_is_skipped_and_reported(tmp_path, loader_four):
  names = [f"tile_{index:02d}.png" for index in range(9)]
  write_random_images(tmp_path, names)
  (tmp_path / "tile_04b.png").write_bytes(b"esto no es una imagen")
  batch = loader_four.load(tmp_path)
  assert batch.tiles_src.shape[0] == 9
  assert batch.skipped == ("tile_04b.png",)
  np.testing.assert_array_equal(batch.tiles_src[5], decode_tile(tmp_path / "tile_05.png"))


def test_batch_without_valid_tiles_fails(tmp_path, loader_one):
  (tmp_path / "bad.jpg").write_bytes(b"nada")
  with pytest.raises(NoValidTilesError, match="no hay teselas válidas"):
    loader_one.load(tmp_path)


def test_unsupported_format_is_skipped(tmp_path, loader_one):
  write_random_images(tmp_path, ["ok.png"])
  Image.new("RGB", (10, 10)).save(tmp_path / "other.gif")
  assert loader_one.load(tmp_path).skipped == ("other.gif",)


# --- Objetivo ---------------------------------------------------------------------


def test_target_4_3_shape(tmp_path):
  Image.new("RGB", (4000, 3000)).save(tmp_path / "target.png")
  target = load_target(tmp_path / "target.png", 100)
  assert target.rows == 75
  assert target.target_src.shape == (75 * CELL_PX, 100 * CELL_PX, RGB_CHANNELS)


def test_very_wide_target_has_one_row(tmp_path):
  Image.new("RGB", (3000, 10)).save(tmp_path / "target.png")
  assert load_target(tmp_path / "target.png", 10).rows == 1


# --- Reutilización -------------------------------------------------------------------


class CountingTargetLoader:
  """Envuelve ``load_target`` contando las decodificaciones."""

  def __init__(self) -> None:
    self.calls = 0

  def __call__(self, path, cols):
    self.calls += 1
    return load_target(path, cols)


class CountingTileLoader:
  """Envuelve un ``TileLoader`` contando las decodificaciones."""

  def __init__(self, loader: TileLoader) -> None:
    self.loader, self.calls = loader, 0

  def load(self, root):
    self.calls += 1
    return self.loader.load(root)


@pytest.fixture
def cached_batch(tmp_path, loader_one):
  write_random_images(tmp_path / "tiles", ["a.png", "b.png"])
  Image.new("RGB", (64, 48)).save(tmp_path / "target.png")
  tiles, target = CountingTileLoader(loader_one), CountingTargetLoader()
  return LoadCache(tiles, target), tiles, target, tmp_path


def test_same_load_is_reused(cached_batch):
  cache, tiles, target, root = cached_batch
  first = cache.load(root / "tiles", root / "target.png", 8)
  second = cache.load(root / "tiles", root / "target.png", 8)
  assert not first.reused and second.reused
  assert (tiles.calls, target.calls) == (1, 1)
  assert second.tiles.tiles_src is first.tiles.tiles_src
  assert second.load_ms >= 0


def test_changing_cols_only_reloads_target(cached_batch):
  cache, tiles, target, root = cached_batch
  cache.load(root / "tiles", root / "target.png", 8)
  second = cache.load(root / "tiles", root / "target.png", 16)
  assert second.tiles_reused and not second.target_reused
  assert (tiles.calls, target.calls) == (1, 2)
  assert second.target.cols == 16
