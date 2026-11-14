"""Entradas validadas de un trabajo y espacio para los buffers de cada backend."""

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.core.constants import CELL_PX, MIN_K, RGB_CHANNELS, TILE_SRC_PX
from app.core.params import InvalidParamsError, MosaicParams

TILES_SRC_SHAPE_TAIL = (TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS)
# Contiguo y escribible: así los backends compilados reciben siempre el mismo
# tipo de array y no recompilan (un array de solo lectura es otro tipo en Numba).
ARRAY_REQUIREMENTS = ("C_CONTIGUOUS", "WRITEABLE")
# Trabajo mínimo de los warmup: dos teselas y una grilla de 1×2 celdas.
WARMUP_TILES = 2
WARMUP_COLS = 2


def _as_kernel_input(array: np.ndarray, dtype: type) -> np.ndarray:
  """Devuelve el array contiguo, escribible y del tipo pedido (copia solo si hace falta)."""
  return np.require(array, dtype=dtype, requirements=ARRAY_REQUIREMENTS)


def _check_tiles(tiles_src: np.ndarray) -> np.ndarray:
  """Valida ``tiles_src [N, 128, 128, 3]`` uint8."""
  if tiles_src.dtype != np.uint8 or tiles_src.ndim != len(TILES_SRC_SHAPE_TAIL) + 1:
    raise InvalidParamsError("tiles_src debe ser uint8 de forma [N, 128, 128, 3]")
  if tiles_src.shape[1:] != TILES_SRC_SHAPE_TAIL or tiles_src.shape[0] == 0:
    raise InvalidParamsError(f"forma de tiles_src inválida: {tiles_src.shape}")
  return _as_kernel_input(tiles_src, np.uint8)


def _check_target(target_src: np.ndarray, cols: int) -> np.ndarray:
  """Valida ``target_src [rows·8, cols·8, 3]`` uint8."""
  if target_src.dtype != np.uint8 or target_src.ndim != len(TILES_SRC_SHAPE_TAIL):
    raise InvalidParamsError("target_src debe ser uint8 de forma [rows·8, cols·8, 3]")
  height, width, channels = target_src.shape
  if channels != RGB_CHANNELS or width != cols * CELL_PX or height % CELL_PX != 0 or height == 0:
    raise InvalidParamsError(f"forma de target_src {target_src.shape} incompatible con cols = {cols}")
  return _as_kernel_input(target_src, np.uint8)


def _check_choice(choice: np.ndarray, n_cells: int, k: int) -> np.ndarray:
  """Valida ``choice [M]`` con valores en ``[0, k)``."""
  if choice.shape != (n_cells,):
    raise InvalidParamsError(f"choice debe tener forma ({n_cells},), recibido {choice.shape}")
  if n_cells and (choice.min() < 0 or choice.max() >= k):
    raise InvalidParamsError(f"los valores de choice deben estar en [0, {k})")
  return _as_kernel_input(choice, np.int32)


@dataclass
class MosaicJob:
  """Un trabajo listo para ejecutar.

  ``buffers`` guarda los arrays intermedios del backend (en CPU, arrays de
  NumPy; en GPU, buffers del dispositivo) entre un paso y el siguiente.
  ``notes`` junta los avisos que terminan en ``MosaicResult.notes``.
  """

  tiles_src: np.ndarray
  target_src: np.ndarray
  params: MosaicParams
  choice: np.ndarray
  rows: int
  buffers: dict[str, Any] = field(default_factory=dict)
  notes: list[str] = field(default_factory=list)

  @classmethod
  def create(
    cls, tiles_src: np.ndarray, target_src: np.ndarray, params: MosaicParams, choice: np.ndarray
  ) -> "MosaicJob":
    """Valida las entradas contra los parámetros y arma el trabajo."""
    tiles = _check_tiles(tiles_src)
    params.validate_for_batch(tiles.shape[0])
    target = _check_target(target_src, params.cols)
    rows = target.shape[0] // CELL_PX
    checked_choice = _check_choice(np.asarray(choice), rows * params.cols, params.k)
    return cls(tiles, target, params, checked_choice, rows)

  @classmethod
  def warmup(cls) -> "MosaicJob":
    """Trabajo mínimo (negro) con los mismos tipos que uno real, para los warmup."""
    tiles_src = np.zeros((WARMUP_TILES, *TILES_SRC_SHAPE_TAIL), dtype=np.uint8)
    target_src = np.zeros((CELL_PX, WARMUP_COLS * CELL_PX, RGB_CHANNELS), dtype=np.uint8)
    params = MosaicParams(cols=WARMUP_COLS, k=MIN_K)
    return cls.create(tiles_src, target_src, params, np.zeros(WARMUP_COLS, dtype=np.int32))

  @property
  def cols(self) -> int:
    """Columnas de la grilla."""
    return self.params.cols

  @property
  def n_tiles(self) -> int:
    """Cantidad de teselas N."""
    return self.tiles_src.shape[0]

  @property
  def n_cells(self) -> int:
    """Cantidad de celdas M = rows · cols."""
    return self.rows * self.cols

  @property
  def output_shape(self) -> tuple[int, int, int]:
    """Forma de la imagen final ``[rows·tile_px, cols·tile_px, 3]``."""
    tile_px = self.params.tile_px
    return (self.rows * tile_px, self.cols * tile_px, RGB_CHANNELS)
