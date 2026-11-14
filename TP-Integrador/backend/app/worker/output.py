"""Guardado de los resultados de un backend, fuera de la medición (design D3).

El worker escribe la imagen a disco para que el proceso web solo la sirva por
ruta: así no viajan arrays entre procesos y la web no codifica imágenes de
cientos de MB.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

PNG_NAME = "mosaico.png"
JPEG_NAME = "mosaico.jpg"
PREVIEW_NAME = "preview.jpg"
# Compresión PNG baja: el archivo pesa más, pero se guarda mucho más rápido.
PNG_COMPRESS_LEVEL = 1
JPEG_QUALITY = 92
PREVIEW_JPEG_QUALITY = 85


@dataclass(frozen=True)
class SavedOutputs:
  """Rutas de los archivos guardados de un resultado."""

  png_path: str
  jpeg_path: str
  preview_path: str


def save_outputs(image: np.ndarray, folder: Path, preview_max_side: int) -> SavedOutputs:
  """Guarda PNG, JPEG y una vista previa reducida a ``preview_max_side`` de lado mayor."""
  folder.mkdir(parents=True, exist_ok=True)
  picture = Image.fromarray(image)
  png_path, jpeg_path, preview_path = folder / PNG_NAME, folder / JPEG_NAME, folder / PREVIEW_NAME
  picture.save(png_path, compress_level=PNG_COMPRESS_LEVEL)
  picture.save(jpeg_path, quality=JPEG_QUALITY)
  picture.thumbnail((preview_max_side, preview_max_side), Image.Resampling.BILINEAR)
  picture.save(preview_path, quality=PREVIEW_JPEG_QUALITY)
  return SavedOutputs(str(png_path), str(jpeg_path), str(preview_path))
