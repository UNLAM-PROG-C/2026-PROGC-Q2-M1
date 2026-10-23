"""Parámetros de un trabajo de fotomosaico, su validación y la derivación de rows."""

import math
from dataclasses import dataclass

from app.core.constants import (
  ALLOWED_TILE_PX,
  DEFAULT_ALPHA,
  DEFAULT_K,
  DEFAULT_SEED,
  DEFAULT_TILE_PX,
  MAX_ALPHA,
  MAX_COLS,
  MAX_K,
  MIN_ALPHA,
  MIN_COLS,
  MIN_K,
  MIN_SEED,
  ROUND_HALF,
)


class InvalidParamsError(ValueError):
  """Parámetros de un trabajo fuera de rango."""


def _require_int_in_range(name: str, value: int, low: int, high: int) -> None:
  """Falla si ``value`` no es un entero en [low, high]."""
  if isinstance(value, bool) or not isinstance(value, int):
    raise InvalidParamsError(f"{name} debe ser un entero (recibido: {value!r})")
  if not low <= value <= high:
    raise InvalidParamsError(f"{name} debe estar entre {low} y {high} (recibido: {value})")


@dataclass(frozen=True)
class MosaicParams:
  """Parámetros de un trabajo; se validan al construirse.

  Attributes:
    cols: columnas de la grilla de celdas.
    tile_px: lado de cada tesela en la imagen final (16, 32 o 64).
    k: candidatos por celda entre los que se sortea la tesela.
    alpha: peso de la tesela en la mezcla con el objetivo, en [0, 1].
    seed: semilla del generador de ``choice``.
  """

  cols: int
  tile_px: int = DEFAULT_TILE_PX
  k: int = DEFAULT_K
  alpha: float = DEFAULT_ALPHA
  seed: int = DEFAULT_SEED

  def __post_init__(self) -> None:
    """Valida los rangos que no dependen del lote."""
    _require_int_in_range("cols", self.cols, MIN_COLS, MAX_COLS)
    if self.tile_px not in ALLOWED_TILE_PX:
      allowed = ", ".join(str(value) for value in ALLOWED_TILE_PX)
      raise InvalidParamsError(f"tile_px debe ser uno de {allowed} (recibido: {self.tile_px})")
    _require_int_in_range("k", self.k, MIN_K, MAX_K)
    if not MIN_ALPHA <= self.alpha <= MAX_ALPHA:
      raise InvalidParamsError(f"alpha debe estar entre {MIN_ALPHA} y {MAX_ALPHA} (recibido: {self.alpha})")
    if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < MIN_SEED:
      raise InvalidParamsError(f"seed debe ser un entero no negativo (recibido: {self.seed!r})")

  def validate_for_batch(self, n_tiles: int) -> None:
    """Valida las reglas que dependen de la cantidad de teselas del lote."""
    if self.k > n_tiles:
      raise InvalidParamsError(f"k no puede superar N, la cantidad de teselas (k = {self.k}, N = {n_tiles})")


def derive_rows(cols: int, width: int, height: int) -> int:
  """Deriva las filas de la grilla: ``max(1, round(cols · alto / ancho))``.

  El redondeo es al entero más cercano con la mitad hacia arriba.
  """
  return max(1, math.floor(cols * height / width + ROUND_HALF))
