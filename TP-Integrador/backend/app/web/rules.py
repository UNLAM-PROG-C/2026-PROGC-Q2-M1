"""Reglas de validación de parámetros que se mandan a la interfaz.

Salen de ``app/core/constants.py`` y de la configuración, así el frontend no
duplica constantes. ``DEFAULT_COLS`` y ``MAX_SEED`` son propios de la
interfaz: el algoritmo no fija columnas por defecto ni un máximo de semilla.
"""

from app.config import Settings
from app.core.constants import (
  ALLOWED_TILE_PX,
  DEFAULT_ALPHA,
  DEFAULT_SEED,
  DEFAULT_TILE_PX,
  MAX_ALPHA,
  MAX_COLS,
  MIN_ALPHA,
  MIN_COLS,
  MIN_SEED,
)

# Columnas que propone el paso 2.
DEFAULT_COLS = 100
# Mayor semilla aceptada: entra en un entero de 32 bits con signo y en un number de JS.
MAX_SEED = 2**31 - 1


def rules_json(settings: Settings) -> dict:
  """Reglas de ``/api/state`` (``ParamRules`` del frontend)."""
  return {
    "cols": {"min": MIN_COLS, "max": MAX_COLS, "default": DEFAULT_COLS},
    "tile_px": {"allowed": list(ALLOWED_TILE_PX), "default": DEFAULT_TILE_PX},
    "alpha": {"min": MIN_ALPHA, "max": MAX_ALPHA, "default": DEFAULT_ALPHA},
    "seed": {"min": MIN_SEED, "max": MAX_SEED, "default": DEFAULT_SEED},
    "max_output_pixels": settings.max_output_pixels,
    "cpu_confirm_seconds": settings.cpu_confirm_seconds,
  }
