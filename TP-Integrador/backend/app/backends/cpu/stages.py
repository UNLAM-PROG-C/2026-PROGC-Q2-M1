"""Etapas del algoritmo en CPU: una función compilada por kernel de GPU.

Cada función recorre con bucles explícitos lo que en GPU es la grilla de hilos:
una iteración del bucle sobre los elementos de salida equivale a un hilo del
kernel del mismo nombre (ver ``kernels/mosaic.cu`` en el cambio 2). Todo se
compila con Numba en modo nopython, de un solo hilo (sin ``parallel``) y sin
vectorización SIMD (ver ``__init__.py``). Las constantes y acumuladores son
float32 para que Numba no promueva a float64 en silencio.

Las funciones auxiliares usan ``inline="always"``: existen para respetar el
largo de función, pero el código generado es el mismo que si estuvieran
escritas dentro del bucle.
"""

import numpy as np
from numba import njit

from app.core.color import (
  CHANNEL_MAX_F32,
  D65_WHITE_F32,
  LAB_A_SCALE_F32,
  LAB_B_SCALE_F32,
  LAB_EPSILON_F32,
  LAB_L_OFFSET_F32,
  LAB_L_SCALE_F32,
  LAB_LINEAR_DIVISOR_F32,
  LAB_LINEAR_OFFSET_F32,
  SRGB_GAMMA_EXPONENT_F32,
  SRGB_GAMMA_OFFSET_F32,
  SRGB_GAMMA_SCALE_F32,
  SRGB_LINEAR_SLOPE_F32,
  SRGB_LINEAR_THRESHOLD_F32,
  SRGB_TO_XYZ_F32,
)
from app.core.constants import CELL_PX, DESC_BLOCK_PX, DESC_DIM, DESC_GRID, RGB_CHANNELS, ROUND_HALF, TILE_SRC_PX

WHITE_X = D65_WHITE_F32[0]
WHITE_Y = D65_WHITE_F32[1]
WHITE_Z = D65_WHITE_F32[2]
ZERO_F32 = np.float32(0.0)
ONE_F32 = np.float32(1.0)
TWO_F32 = np.float32(2.0)
ROUND_HALF_F32 = np.float32(ROUND_HALF)
DESC_BLOCK_AREA_F32 = np.float32(DESC_BLOCK_PX * DESC_BLOCK_PX)
# Relleno inicial del top-k: (+∞, mayor índice posible) pierde siempre.
TOPK_EMPTY_DIST = np.float32(np.inf)
TOPK_EMPTY_IDX = np.iinfo(np.int32).max

# --- Conversión de color ---------------------------------------------------------


@njit(inline="always")
def linearize(channel):
  """Inversa de la curva gamma de sRGB para un canal en [0, 255]."""
  value = np.float32(channel) / CHANNEL_MAX_F32
  if value <= SRGB_LINEAR_THRESHOLD_F32:
    return value / SRGB_LINEAR_SLOPE_F32
  return np.power((value + SRGB_GAMMA_OFFSET_F32) / SRGB_GAMMA_SCALE_F32, SRGB_GAMMA_EXPONENT_F32)


@njit(inline="always")
def lab_f(t):
  """Función f(t) de CIELAB."""
  if t > LAB_EPSILON_F32:
    return np.cbrt(t)
  return t / LAB_LINEAR_DIVISOR_F32 + LAB_LINEAR_OFFSET_F32


@njit(inline="always")
def srgb_to_lab(red, green, blue):
  """Convierte un color sRGB (canales en [0, 255]) a Lab en float32."""
  r, g, b = linearize(red), linearize(green), linearize(blue)
  m = SRGB_TO_XYZ_F32
  fx = lab_f((m[0, 0] * r + m[0, 1] * g + m[0, 2] * b) / WHITE_X)
  fy = lab_f((m[1, 0] * r + m[1, 1] * g + m[1, 2] * b) / WHITE_Y)
  fz = lab_f((m[2, 0] * r + m[2, 1] * g + m[2, 2] * b) / WHITE_Z)
  lightness = LAB_L_SCALE_F32 * fy - LAB_L_OFFSET_F32
  return lightness, LAB_A_SCALE_F32 * (fx - fy), LAB_B_SCALE_F32 * (fy - fz)


# --- Preparación de teselas ------------------------------------------------------


@njit(inline="always")
def block_mean_rounded(tiles_src, tile, y0, x0, channel, factor):
  """Promedio entero redondeado de un bloque ``factor×factor`` de un canal."""
  area = factor * factor
  total = 0
  for dy in range(factor):
    for dx in range(factor):
      total += tiles_src[tile, y0 + dy, x0 + dx, channel]
  return (total + area // 2) // area


@njit(cache=False)
def resize_tiles(tiles_src, tile_px, tiles_px):
  """Reduce cada tesela de 128×128 a ``tile_px``×``tile_px`` promediando bloques."""
  factor = TILE_SRC_PX // tile_px
  for tile in range(tiles_src.shape[0]):
    for y in range(tile_px):
      for x in range(tile_px):
        # Una iteración (tile, y, x) = un hilo del kernel resize_tiles.
        for channel in range(RGB_CHANNELS):
          tiles_px[tile, y, x, channel] = block_mean_rounded(tiles_src, tile, y * factor, x * factor, channel, factor)


@njit(inline="always")
def block_mean_srgb(tiles_src, tile, y0, x0, channel):
  """Promedio float32 de un canal en un bloque de 16×16 de la tesela fuente."""
  total = 0
  for dy in range(DESC_BLOCK_PX):
    for dx in range(DESC_BLOCK_PX):
      total += tiles_src[tile, y0 + dy, x0 + dx, channel]
  return np.float32(total) / DESC_BLOCK_AREA_F32


@njit(inline="always")
def write_lab(desc, row, position, red, green, blue):
  """Convierte un color a Lab y lo escribe en la posición ``position`` del descriptor."""
  lightness, a, b = srgb_to_lab(red, green, blue)
  offset = position * RGB_CHANNELS
  desc[row, offset] = lightness
  desc[row, offset + 1] = a
  desc[row, offset + 2] = b


@njit(cache=False)
def tile_descriptors(tiles_src, tile_desc):
  """Miniatura Lab 8×8 de cada tesela: promedio sRGB de bloques 16×16 y conversión."""
  for tile in range(tiles_src.shape[0]):
    for cy in range(DESC_GRID):
      for cx in range(DESC_GRID):
        # Una iteración (tile, cy, cx) = un hilo del kernel tile_descriptors.
        y0, x0 = cy * DESC_BLOCK_PX, cx * DESC_BLOCK_PX
        red = block_mean_srgb(tiles_src, tile, y0, x0, 0)
        green = block_mean_srgb(tiles_src, tile, y0, x0, 1)
        blue = block_mean_srgb(tiles_src, tile, y0, x0, 2)
        write_lab(tile_desc, tile, cy * DESC_GRID + cx, red, green, blue)


# --- Descriptores del objetivo ---------------------------------------------------


@njit(cache=False)
def cell_descriptors(target_src, cols, cell_desc):
  """Convierte a Lab cada píxel del bloque 8×8 de cada celda, en orden de filas."""
  for cell in range(cell_desc.shape[0]):
    y0, x0 = (cell // cols) * CELL_PX, (cell % cols) * CELL_PX
    for py in range(CELL_PX):
      for px in range(CELL_PX):
        # Una iteración (cell, py, px) = un hilo del kernel cell_descriptors.
        pixel = target_src[y0 + py, x0 + px]
        write_lab(cell_desc, cell, py * CELL_PX + px, pixel[0], pixel[1], pixel[2])


@njit(cache=False)
def sq_norms(desc, norms):
  """Norma al cuadrado de cada descriptor, sumando en orden 0..191."""
  for row in range(desc.shape[0]):
    # Una iteración = un hilo del kernel sq_norms.
    total = ZERO_F32
    for d in range(DESC_DIM):
      total += desc[row, d] * desc[row, d]
    norms[row] = total


# --- Matching ------------------------------------------------------------------------


@njit(cache=False)
def distances(cell_desc, tile_desc, cell_norms, tile_norms, row_offset, dist):
  """Distancias ``(‖c‖² + ‖t‖²) − 2·c·t`` de un bloque de celdas a todas las teselas."""
  for r in range(dist.shape[0]):
    cell = row_offset + r
    for tile in range(tile_desc.shape[0]):
      # Una iteración (r, tile) = un hilo del kernel distances_tiled.
      dot = ZERO_F32
      for d in range(DESC_DIM):
        dot += cell_desc[cell, d] * tile_desc[tile, d]
      dist[r, tile] = (cell_norms[cell] + tile_norms[tile]) - TWO_F32 * dot


@njit(inline="always")
def precedes(dist_a, idx_a, dist_b, idx_b):
  """Orden lexicográfico (distancia, índice): ante igual distancia gana el índice menor."""
  return dist_a < dist_b or (dist_a == dist_b and idx_a < idx_b)


@njit(inline="always")
def insert_sorted(best_dist, best_idx, dist, idx):
  """Inserta (dist, idx) en el arreglo ordenado de tamaño k si entra."""
  pos = best_dist.shape[0] - 1
  if not precedes(dist, idx, best_dist[pos], best_idx[pos]):
    return
  while pos > 0 and precedes(dist, idx, best_dist[pos - 1], best_idx[pos - 1]):
    best_dist[pos] = best_dist[pos - 1]
    best_idx[pos] = best_idx[pos - 1]
    pos -= 1
  best_dist[pos] = dist
  best_idx[pos] = idx


@njit(cache=False)
def topk_rows(dist, row_offset, topk_idx, topk_dist):
  """Top-k de cada fila del bloque: un recorrido de las N teselas con inserción ordenada."""
  k = topk_idx.shape[1]
  best_dist = np.empty(k, dtype=np.float32)
  best_idx = np.empty(k, dtype=np.int32)
  for r in range(dist.shape[0]):
    # Una iteración = el trabajo de un bloque de hilos del kernel topk_rows.
    best_dist[:] = TOPK_EMPTY_DIST
    best_idx[:] = TOPK_EMPTY_IDX
    for tile in range(dist.shape[1]):
      insert_sorted(best_dist, best_idx, dist[r, tile], tile)
    topk_idx[row_offset + r, :] = best_idx
    topk_dist[row_offset + r, :] = best_dist


# --- Composición ----------------------------------------------------------------------


@njit(inline="always")
def blend(tile_value, target_value, alpha):
  """Mezcla ``round(alpha·tesela + (1 − alpha)·objetivo)`` en float32."""
  mixed = alpha * np.float32(tile_value) + (ONE_F32 - alpha) * np.float32(target_value)
  return np.uint8(mixed + ROUND_HALF_F32)


@njit(cache=False)
def compose(tiles_px, target_src, topk_idx, choice, cols, alpha, out):
  """Arma la imagen final con la tesela elegida de cada celda, mezclada con el objetivo."""
  tile_px = tiles_px.shape[1]
  scale = tile_px // CELL_PX
  for y in range(out.shape[0]):
    for x in range(out.shape[1]):
      # Una iteración (y, x) = un hilo del kernel compose.
      cell = (y // tile_px) * cols + x // tile_px
      tile = topk_idx[cell, choice[cell]]
      for channel in range(RGB_CHANNELS):
        tile_value = tiles_px[tile, y % tile_px, x % tile_px, channel]
        out[y, x, channel] = blend(tile_value, target_src[y // scale, x // scale, channel], alpha)
