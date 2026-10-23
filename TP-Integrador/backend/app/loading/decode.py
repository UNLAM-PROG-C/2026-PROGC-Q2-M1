"""Decodificación y normalización de imágenes.

``decode_into_shared`` es la tarea que ejecutan los procesos del pool de
decodificación (consumidores): abre el bloque de memoria compartida por nombre
y escribe la tesela en su posición, sin devolver píxeles por la cola.
"""

from multiprocessing import shared_memory
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from app.core.constants import RGB_CHANNELS, SUPPORTED_IMAGE_FORMATS, TILE_SRC_PX

RGB_MODE = "RGB"
TILE_SHAPE = (TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS)


class UnsupportedImageError(ValueError):
  """El archivo es una imagen, pero no de un formato admitido."""


def open_rgb(path: str | Path) -> Image.Image:
  """Abre una imagen admitida, aplica la orientación EXIF y la pasa a RGB."""
  with Image.open(path) as image:
    if image.format not in SUPPORTED_IMAGE_FORMATS:
      raise UnsupportedImageError(f"formato no admitido: {image.format}")
    oriented = ImageOps.exif_transpose(image)
    return oriented.convert(RGB_MODE)


def center_square(image: Image.Image) -> Image.Image:
  """Recorta el cuadrado central de la imagen."""
  width, height = image.size
  side = min(width, height)
  left = (width - side) // 2
  top = (height - side) // 2
  return image.crop((left, top, left + side, top + side))


def normalize_tile(image: Image.Image) -> np.ndarray:
  """Convierte una imagen RGB en una tesela ``[128, 128, 3]`` uint8."""
  square = center_square(image)
  resized = square.resize((TILE_SRC_PX, TILE_SRC_PX), Image.Resampling.LANCZOS)
  return np.array(resized, dtype=np.uint8)


def decode_tile(path: str | Path) -> np.ndarray:
  """Decodifica un archivo y devuelve su tesela normalizada."""
  return normalize_tile(open_rgb(path))


def attach_shared_memory(name: str) -> shared_memory.SharedMemory:
  """Se conecta a un bloque compartido existente sin registrarlo para borrarlo."""
  try:
    return shared_memory.SharedMemory(name=name, track=False)
  except TypeError:  # Python < 3.13 no tiene el parámetro track.
    return shared_memory.SharedMemory(name=name)


def decode_into_shared(task: tuple[str, int, str, int]) -> tuple[int, str | None]:
  """Decodifica una tesela y la escribe en ``tiles[index]`` del bloque compartido.

  Args:
    task: ``(ruta, índice, nombre del bloque compartido, N)``.

  Returns:
    ``(índice, None)`` si salió bien, o ``(índice, motivo)`` si el archivo es inválido.
  """
  path, index, shm_name, n_tiles = task
  try:
    tile = decode_tile(path)
  except Exception as error:  # Cualquier falla de decodificación invalida el archivo.
    return index, f"{type(error).__name__}: {error}"
  block = attach_shared_memory(shm_name)
  try:
    np.ndarray((n_tiles, *TILE_SHAPE), dtype=np.uint8, buffer=block.buf)[index] = tile
  finally:
    block.close()
  return index, None
