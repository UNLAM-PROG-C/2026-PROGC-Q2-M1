"""Constantes compartidas por los kernels de CUDA y OpenCL (design D1 del cambio 2).

Los archivos ``kernels/mosaic.cu`` y ``kernels/mosaic.cl`` no tienen literales
con significado de negocio: cada constante llega como ``-DNOMBRE=valor``
generada acá a partir de ``app/core/constants.py`` y ``app/core/color.py``, la
misma fuente que usa el backend CPU. Los floats se escriben con el valor exacto
de su copia float32 y sufijo ``f``, así la GPU usa los mismos bits que Numba.
"""

from pathlib import Path

import numpy as np

from app.core import color
from app.core.constants import (
  BLOCK_1D,
  CELL_PX,
  COMPOSE_TILE,
  DESC_BLOCK_PX,
  DESC_DIM,
  DESC_GRID,
  MATMUL_TILE,
  MAX_K,
  RGB_CHANNELS,
  ROUND_HALF,
  TILE_SRC_PX,
  TOPK_THREADS,
)

# Carpeta de los kernels: backend/kernels/.
KERNELS_DIR = Path(__file__).resolve().parents[2] / "kernels"
CUDA_SOURCE_NAME = "mosaic.cu"
OPENCL_SOURCE_NAME = "mosaic.cl"
# Ejes de la matriz sRGB → XYZ y del blanco D65, en el orden de los nombres.
XYZ_AXES = "XYZ"
ASCII = "ascii"
ASCII_REPLACEMENT = "replace"

INT_DEFINES = {
  "TILE_SRC_PX": TILE_SRC_PX,
  "RGB_CHANNELS": RGB_CHANNELS,
  "DESC_GRID": DESC_GRID,
  "DESC_BLOCK_PX": DESC_BLOCK_PX,
  "DESC_DIM": DESC_DIM,
  "CELL_PX": CELL_PX,
  "BLOCK_1D": BLOCK_1D,
  "MATMUL_TILE": MATMUL_TILE,
  "TOPK_THREADS": TOPK_THREADS,
  "MAX_K": MAX_K,
  "COMPOSE_TILE": COMPOSE_TILE,
}

FLOAT_DEFINES = {
  "CHANNEL_MAX": color.CHANNEL_MAX_F32,
  "ROUND_HALF": np.float32(ROUND_HALF),
  "SRGB_LINEAR_THRESHOLD": color.SRGB_LINEAR_THRESHOLD_F32,
  "SRGB_LINEAR_SLOPE": color.SRGB_LINEAR_SLOPE_F32,
  "SRGB_GAMMA_OFFSET": color.SRGB_GAMMA_OFFSET_F32,
  "SRGB_GAMMA_SCALE": color.SRGB_GAMMA_SCALE_F32,
  "SRGB_GAMMA_EXPONENT": color.SRGB_GAMMA_EXPONENT_F32,
  "LAB_EPSILON": color.LAB_EPSILON_F32,
  "LAB_LINEAR_DIVISOR": color.LAB_LINEAR_DIVISOR_F32,
  "LAB_LINEAR_OFFSET": color.LAB_LINEAR_OFFSET_F32,
  "LAB_L_SCALE": color.LAB_L_SCALE_F32,
  "LAB_L_OFFSET": color.LAB_L_OFFSET_F32,
  "LAB_A_SCALE": color.LAB_A_SCALE_F32,
  "LAB_B_SCALE": color.LAB_B_SCALE_F32,
}


def float_literal(value: float) -> str:
  """Literal C de un float32: el valor exacto de la copia float32 con sufijo ``f``."""
  return f"{float(np.float32(value))!r}f"


def _color_matrix_defines() -> dict[str, np.float32]:
  """``SRGB_TO_XYZ_<fila><columna>`` y ``WHITE_<eje>`` en float32."""
  defines = {}
  for row, row_axis in enumerate(XYZ_AXES):
    defines[f"WHITE_{row_axis}"] = color.D65_WHITE_F32[row]
    for col in range(len(XYZ_AXES)):
      defines[f"SRGB_TO_XYZ_{row}{col}"] = color.SRGB_TO_XYZ_F32[row, col]
  return defines


def kernel_defines() -> dict[str, str]:
  """Nombre → literal C de todas las constantes que usan los kernels."""
  floats = {**FLOAT_DEFINES, **_color_matrix_defines()}
  defines = {name: str(value) for name, value in INT_DEFINES.items()}
  defines.update({name: float_literal(value) for name, value in floats.items()})
  return defines


def define_options() -> list[str]:
  """Opciones ``-DNOMBRE=valor`` para ``SourceModule`` (CUDA) y ``Program.build`` (OpenCL)."""
  return [f"-D{name}={value}" for name, value in kernel_defines().items()]


def load_kernel_source(file_name: str) -> str:
  """Lee el código fuente de un kernel de ``backend/kernels`` como ASCII.

  Los archivos están en UTF-8 y solo los comentarios tienen caracteres no ASCII
  (tildes, ``‖``, ``·``...). PyCUDA escribe el fuente a un archivo temporal con
  la codificación del sistema (cp1252 en Windows), que no puede representar
  algunos de esos caracteres; por eso se reemplazan por ``?`` antes de compilar.
  """
  source = (KERNELS_DIR / file_name).read_text(encoding="utf-8")
  return source.encode(ASCII, errors=ASCII_REPLACEMENT).decode(ASCII)
