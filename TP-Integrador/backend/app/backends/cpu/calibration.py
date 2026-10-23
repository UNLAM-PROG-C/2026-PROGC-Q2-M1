"""Calibración del backend CPU para estimar la duración de un trabajo (design D8).

Después del ``warmup()`` se ejecutan las etapas sobre un problema sintético
fijo y se obtienen costos unitarios medidos en esta máquina (una constante no
sería portable):

- ``matching_ns_per_pair``: ns por par celda-tesela del matching + top-k;
- ``prepare_ns_per_pixel``: ns por píxel de tesela preparada (``N·tile_px²``);
- ``compose_ns_per_pixel``: ns por píxel compuesto (``M·tile_px²``); incluye
  también los descriptores del objetivo, que crecen con M y pesan poco.

La estimación es ``pares·c_pares + píxeles·c_píxeles``. Vive acá (y no en el
worker) para que el benchmark del cambio 5 la reutilice.
"""

from dataclasses import dataclass

import numpy as np

from app.core.backend import MosaicBackend
from app.core.choice import generate_choice
from app.core.constants import CELL_PX, DEFAULT_K, DEFAULT_TILE_PX, RGB_CHANNELS, TILE_SRC_PX
from app.core.params import MosaicParams

# Problema sintético fijo: chico para tardar poco, grande para medir algo estable.
CALIBRATION_TILES = 256
CALIBRATION_ROWS = 24
CALIBRATION_COLS = 32
CALIBRATION_SEED = 2024
CHANNEL_LEVELS = 256
NS_PER_MS = 1_000_000
NS_PER_SECOND = 1_000_000_000


@dataclass(frozen=True)
class CpuCalibration:
  """Costos unitarios del backend CPU en nanosegundos."""

  matching_ns_per_pair: float
  prepare_ns_per_pixel: float
  compose_ns_per_pixel: float


def _synthetic_inputs() -> tuple[np.ndarray, np.ndarray]:
  """Teselas y objetivo de ruido reproducibles."""
  rng = np.random.default_rng(CALIBRATION_SEED)
  tiles = rng.integers(0, CHANNEL_LEVELS, (CALIBRATION_TILES, TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS), dtype=np.uint8)
  target_shape = (CALIBRATION_ROWS * CELL_PX, CALIBRATION_COLS * CELL_PX, RGB_CHANNELS)
  return tiles, rng.integers(0, CHANNEL_LEVELS, target_shape, dtype=np.uint8)


def calibrate_cpu(backend: MosaicBackend) -> CpuCalibration:
  """Ejecuta el problema sintético en ``backend`` (ya precalentado) y deriva los costos."""
  tiles, target = _synthetic_inputs()
  params = MosaicParams(cols=CALIBRATION_COLS, tile_px=DEFAULT_TILE_PX, k=DEFAULT_K, seed=CALIBRATION_SEED)
  m_cells = CALIBRATION_ROWS * CALIBRATION_COLS
  choice = generate_choice(params.seed, params.k, m_cells)
  timings = backend.run(tiles, target, params, choice).timings
  tile_pixels = params.tile_px * params.tile_px
  return CpuCalibration(
    matching_ns_per_pair=timings.matching_ms * NS_PER_MS / (m_cells * CALIBRATION_TILES),
    prepare_ns_per_pixel=timings.prepare_tiles_ms * NS_PER_MS / (CALIBRATION_TILES * tile_pixels),
    compose_ns_per_pixel=(timings.compose_ms + timings.target_descriptors_ms) * NS_PER_MS / (m_cells * tile_pixels),
  )


def estimate_cpu_seconds(calibration: CpuCalibration, n_tiles: int, m_cells: int, tile_px: int) -> float:
  """Segundos estimados de un trabajo en CPU (la misma fórmula usa la interfaz)."""
  tile_pixels = tile_px * tile_px
  matching_ns = m_cells * n_tiles * calibration.matching_ns_per_pair
  prepare_ns = n_tiles * tile_pixels * calibration.prepare_ns_per_pixel
  compose_ns = m_cells * tile_pixels * calibration.compose_ns_per_pixel
  return (matching_ns + prepare_ns + compose_ns) / NS_PER_SECOND
