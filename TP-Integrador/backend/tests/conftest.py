"""Fábricas de lotes sintéticos con semilla y fixtures compartidas."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.backends.cpu.backend import CpuBackend
from app.core.constants import CELL_PX, RGB_CHANNELS, TILE_SRC_PX

SYNTHETIC_SEED = 1234
CHANNEL_LEVELS = 256
SYNTHETIC_IMAGE_PX = 48


def solid_tiles(colors: list[tuple[int, int, int]]) -> np.ndarray:
  """Una tesela de 128×128 de color uniforme por cada color."""
  tiles = np.empty((len(colors), TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS), dtype=np.uint8)
  tiles[:] = np.asarray(colors, dtype=np.uint8)[:, None, None, :]
  return tiles


def random_tiles(n_tiles: int, seed: int = SYNTHETIC_SEED) -> np.ndarray:
  """``n_tiles`` teselas de ruido uniforme, reproducibles por semilla."""
  rng = np.random.default_rng(seed)
  return rng.integers(0, CHANNEL_LEVELS, (n_tiles, TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS), dtype=np.uint8)


def random_target(rows: int, cols: int, seed: int = SYNTHETIC_SEED) -> np.ndarray:
  """``target_src`` de ruido uniforme para una grilla de ``rows × cols``."""
  rng = np.random.default_rng(seed)
  return rng.integers(0, CHANNEL_LEVELS, (rows * CELL_PX, cols * CELL_PX, RGB_CHANNELS), dtype=np.uint8)


def target_from_cell_colors(cell_colors: np.ndarray) -> np.ndarray:
  """``target_src`` donde cada celda es un bloque 8×8 del color de ``cell_colors[fila, col]``."""
  return np.repeat(np.repeat(cell_colors.astype(np.uint8), CELL_PX, axis=0), CELL_PX, axis=1)


def write_random_images(folder: Path, names: list[str], seed: int = SYNTHETIC_SEED) -> None:
  """Escribe imágenes PNG de ruido con los nombres (rutas relativas) pedidos."""
  rng = np.random.default_rng(seed)
  for name in names:
    pixels = rng.integers(0, CHANNEL_LEVELS, (SYNTHETIC_IMAGE_PX, SYNTHETIC_IMAGE_PX, RGB_CHANNELS), dtype=np.uint8)
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels).save(path)


@pytest.fixture(scope="session")
def cpu_backend() -> CpuBackend:
  """Backend CPU ya inicializado (la compilación se paga una vez por sesión)."""
  backend = CpuBackend()
  backend.warmup()
  return backend
