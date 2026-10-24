"""Datos sintéticos reproducibles del benchmark (design D2 del cambio 5).

La etapa común de carga no se compara, así que el benchmark arma ``tiles_src``
y ``target_src`` directamente en memoria, a partir de una semilla:

- cada tesela es un degradado entre dos colores al azar, en una dirección al
  azar, con una textura de ruido de baja amplitud: hay variedad de
  descriptores y casi no hay empates exactos en el top-k;
- el objetivo es un campo suave: el promedio de colores al azar pesado por
  gaussianas, de forma ``[rows·8, cols·8, 3]``.
"""

import math

import numpy as np

from app.bench.defaults import (
  TARGET_ASPECT_COLS,
  TARGET_ASPECT_ROWS,
  TARGET_BLOB_MAX_SIGMA,
  TARGET_BLOB_MIN_SIGMA,
  TARGET_BLOBS,
  TARGET_WEIGHT_EPSILON,
  TILE_CHUNK,
  TILE_NOISE_AMPLITUDE,
)
from app.core.constants import CELL_PX, MAX_CHANNEL_VALUE, MAX_COLS, RGB_CHANNELS, TILE_SRC_PX

TARGET_LOG_ASPECT = math.log(TARGET_ASPECT_COLS / TARGET_ASPECT_ROWS)
# Generadores independientes para teselas y objetivo a partir de la misma semilla.
TILES_STREAM = 0
TARGET_STREAM = 1


def grid_shape(m_cells: int) -> tuple[int, int]:
  """``(rows, cols)`` con ``rows·cols = M`` y ``cols/rows`` lo más cerca posible de 4:3."""
  # Siempre existe (M, 1); las grillas de más de MAX_COLS columnas no las acepta MosaicParams.
  candidates = [(rows, m_cells // rows) for rows in range(1, m_cells + 1) if m_cells % rows == 0]
  valid = [(rows, cols) for rows, cols in candidates if cols <= MAX_COLS]
  return min(valid, key=lambda shape: abs(math.log(shape[1] / shape[0]) - TARGET_LOG_ASPECT))


def _gradient_positions(angles: np.ndarray) -> np.ndarray:
  """Posición en [0, 1] de cada píxel a lo largo de la dirección de cada tesela ``[n, 128, 128, 1]``."""
  coords = np.linspace(0.0, 1.0, TILE_SRC_PX, dtype=np.float32)
  cos, sin = np.cos(angles), np.sin(angles)
  projection = cos * coords[None, None, :, None] + sin * coords[None, :, None, None]
  low = np.minimum(cos, 0.0) + np.minimum(sin, 0.0)
  return (projection - low) / (np.abs(cos) + np.abs(sin))


def _tile_chunk(rng: np.random.Generator, count: int) -> np.ndarray:
  """``count`` teselas: degradado entre dos colores más ruido, en uint8."""
  start = rng.uniform(0.0, MAX_CHANNEL_VALUE, (count, 1, 1, RGB_CHANNELS)).astype(np.float32)
  end = rng.uniform(0.0, MAX_CHANNEL_VALUE, (count, 1, 1, RGB_CHANNELS)).astype(np.float32)
  angles = rng.uniform(0.0, math.tau, (count, 1, 1, 1)).astype(np.float32)
  noise = rng.uniform(-TILE_NOISE_AMPLITUDE, TILE_NOISE_AMPLITUDE, (count, TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS))
  pixels = start + (end - start) * _gradient_positions(angles) + noise.astype(np.float32)
  return np.rint(np.clip(pixels, 0.0, MAX_CHANNEL_VALUE)).astype(np.uint8)


def synthetic_tiles(n_tiles: int, seed: int) -> np.ndarray:
  """``tiles_src [N, 128, 128, 3]`` uint8, generado por bloques para acotar la memoria."""
  rng = np.random.default_rng((seed, TILES_STREAM))
  tiles = np.empty((n_tiles, TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS), dtype=np.uint8)
  for first in range(0, n_tiles, TILE_CHUNK):
    count = min(TILE_CHUNK, n_tiles - first)
    tiles[first : first + count] = _tile_chunk(rng, count)
  return tiles


def _gaussian(rng: np.random.Generator, height: int, width: int) -> np.ndarray:
  """Peso ``[alto, ancho]`` de una gaussiana de centro y ancho al azar (separable)."""
  sigma = rng.uniform(TARGET_BLOB_MIN_SIGMA, TARGET_BLOB_MAX_SIGMA) * min(height, width)
  center_y, center_x = rng.uniform(0.0, height), rng.uniform(0.0, width)
  weight_y = np.exp(-0.5 * ((np.arange(height) - center_y) / sigma) ** 2)
  weight_x = np.exp(-0.5 * ((np.arange(width) - center_x) / sigma) ** 2)
  return np.outer(weight_y, weight_x)


def synthetic_target(rows: int, cols: int, seed: int) -> np.ndarray:
  """``target_src [rows·8, cols·8, 3]`` uint8: promedio de colores pesado por gaussianas."""
  rng = np.random.default_rng((seed, TARGET_STREAM))
  height, width = rows * CELL_PX, cols * CELL_PX
  colors = np.zeros((height, width, RGB_CHANNELS))
  weights = np.full((height, width), TARGET_WEIGHT_EPSILON)
  for _ in range(TARGET_BLOBS):
    color = rng.uniform(0.0, MAX_CHANNEL_VALUE, RGB_CHANNELS)
    weight = _gaussian(rng, height, width)
    colors += weight[..., None] * color
    weights += weight
  return np.rint(colors / weights[..., None]).astype(np.uint8)
