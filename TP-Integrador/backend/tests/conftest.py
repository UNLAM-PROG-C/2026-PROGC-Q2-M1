"""Fábricas de lotes sintéticos con semilla y fixtures compartidas."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.backends.cpu.backend import CpuBackend
from app.backends.registry import BackendRegistry
from app.core.backend import MosaicBackend
from app.core.constants import CELL_PX, DESC_BLOCK_PX, DESC_GRID, RGB_CHANNELS, TILE_SRC_PX
from app.core.result import StageTimings

SYNTHETIC_SEED = 1234
CHANNEL_LEVELS = 256
SYNTHETIC_IMAGE_PX = 48
# Marca que deja ``mark_end_of_measurement`` en el registro de llamadas.
END_OF_MEASUREMENT = ("end_of_measurement",)


def solid_tiles(colors: list[tuple[int, int, int]]) -> np.ndarray:
  """Una tesela de 128×128 de color uniforme por cada color."""
  tiles = np.empty((len(colors), TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS), dtype=np.uint8)
  tiles[:] = np.asarray(colors, dtype=np.uint8)[:, None, None, :]
  return tiles


def random_tiles(n_tiles: int, seed: int = SYNTHETIC_SEED) -> np.ndarray:
  """``n_tiles`` teselas de ruido uniforme, reproducibles por semilla."""
  rng = np.random.default_rng(seed)
  return rng.integers(0, CHANNEL_LEVELS, (n_tiles, TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS), dtype=np.uint8)


def blocky_tiles(n_tiles: int, seed: int = SYNTHETIC_SEED) -> np.ndarray:
  """Teselas cuyos bloques de 16×16 son de un color uniforme al azar.

  A diferencia del ruido por píxel (cuyos promedios quedan todos cerca del gris),
  sus descriptores están bien separados: sirven para comparar backends sin una
  avalancha de casi-empates.
  """
  rng = np.random.default_rng(seed)
  small = rng.integers(0, CHANNEL_LEVELS, (n_tiles, DESC_GRID, DESC_GRID, RGB_CHANNELS), dtype=np.uint8)
  return np.repeat(np.repeat(small, DESC_BLOCK_PX, axis=1), DESC_BLOCK_PX, axis=2)


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
def backend_registry():
  """Registro real: detecta y precalienta CPU, CUDA y OpenCL una vez por sesión."""
  with BackendRegistry() as registry:
    registry.detect_and_warmup()
    yield registry


def require_backend(registry: BackendRegistry, name: str) -> MosaicBackend:
  """Backend del registro, o ``skip`` con el motivo legible si no está disponible."""
  status = registry.status(name)
  if not status.available:
    pytest.skip(f"{status.display_name} no disponible: {status.reason}")
  return registry.resolve([name])[0]


@pytest.fixture(scope="session")
def cpu_backend() -> CpuBackend:
  """Backend CPU ya inicializado (la compilación se paga una vez por sesión)."""
  backend = CpuBackend()
  backend.warmup()
  return backend


def spy(monkeypatch, owner, attribute: str, log: list, describe) -> None:
  """Envuelve ``owner.attribute`` para anotar ``describe(*args, **kwargs)`` en ``log`` antes de llamarlo."""
  real = getattr(owner, attribute)

  def wrapper(*args, **kwargs):
    log.append(describe(*args, **kwargs))
    return real(*args, **kwargs)

  monkeypatch.setattr(owner, attribute, wrapper)


def mark_end_of_measurement(monkeypatch, log: list) -> None:
  """Anota en ``log`` el momento en que ``BaseBackend`` cierra la medición (arma los tiempos)."""
  real = StageTimings.from_elapsed

  def from_elapsed(cls, elapsed_ms, total_ms):
    log.append(END_OF_MEASUREMENT)
    return real(elapsed_ms, total_ms)

  monkeypatch.setattr(StageTimings, "from_elapsed", classmethod(from_elapsed))
