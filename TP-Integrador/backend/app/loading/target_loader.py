"""Preparación de la imagen objetivo y derivación de la grilla."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.constants import CELL_PX
from app.core.params import derive_rows
from app.loading.decode import open_rgb


class InvalidTargetError(ValueError):
  """La imagen objetivo no se pudo decodificar."""


@dataclass(frozen=True)
class TargetImage:
  """Imagen objetivo lista para los backends.

  Attributes:
    target_src: ``[rows·8, cols·8, 3]`` uint8.
    rows: filas de la grilla.
    cols: columnas de la grilla.
  """

  target_src: np.ndarray
  rows: int
  cols: int


def prepare_target(image: Image.Image, cols: int) -> TargetImage:
  """Redimensiona una imagen RGB a exactamente ``(cols·8, rows·8)``."""
  width, height = image.size
  rows = derive_rows(cols, width, height)
  resized = image.resize((cols * CELL_PX, rows * CELL_PX), Image.Resampling.LANCZOS)
  return TargetImage(np.array(resized, dtype=np.uint8), rows, cols)


def load_target(path: str | Path, cols: int) -> TargetImage:
  """Decodifica la imagen objetivo (EXIF, RGB) y la prepara para ``cols`` columnas."""
  try:
    image = open_rgb(path)
  except Exception as error:  # Cualquier falla de decodificación invalida el objetivo.
    raise InvalidTargetError(f"no se pudo decodificar la imagen objetivo: {error}") from error
  return prepare_target(image, cols)
