"""Carga del lote de teselas con un pool de procesos (Productor/Consumidor).

El proceso padre (productor) asigna a cada archivo su índice según el orden
lexicográfico de las rutas relativas y reparte tareas ``(ruta, índice, nombre
del bloque compartido)``. Los procesos del pool (consumidores) decodifican y
escriben cada tesela directamente en su posición de un ``SharedMemory`` de
``[N, 128, 128, 3]``: los píxeles nunca viajan por las colas del pool. Como el
índice está fijado de antemano, el resultado no depende de cuántos procesos
haya ni del orden en que terminen.

Se usa siempre el contexto ``spawn`` (design D7).
"""

import multiprocessing
import os
from dataclasses import dataclass
from multiprocessing import shared_memory
from pathlib import Path

import numpy as np

from app.loading.decode import TILE_SHAPE, decode_into_shared

START_METHOD = "spawn"
# Tareas que recibe cada proceso del pool por envío.
DECODE_CHUNKSIZE = 8


class NoValidTilesError(ValueError):
  """Ningún archivo del lote se pudo decodificar."""


@dataclass(frozen=True)
class TileBatch:
  """Lote de teselas normalizado.

  Attributes:
    tiles_src: ``[N, 128, 128, 3]`` uint8, en el orden de ``paths``.
    paths: rutas relativas (con ``/``) de las teselas válidas.
    skipped: rutas relativas de los archivos omitidos por inválidos.
  """

  tiles_src: np.ndarray
  paths: tuple[str, ...]
  skipped: tuple[str, ...]


def list_batch_files(root: str | Path) -> list[str]:
  """Lista los archivos del lote como rutas relativas, en orden lexicográfico."""
  base = Path(root)
  files = (path for path in base.rglob("*") if path.is_file())
  return sorted(path.relative_to(base).as_posix() for path in files)


def default_workers() -> int:
  """Cantidad de procesos de decodificación por defecto: uno por núcleo."""
  return os.cpu_count() or 1


class TileLoader:
  """Decodifica lotes de teselas; el pool se crea una vez y se reutiliza."""

  def __init__(self, workers: int | None = None) -> None:
    """Configura la cantidad de procesos; el pool se crea en la primera carga."""
    self.workers = workers or default_workers()
    self._pool = None

  def __enter__(self) -> "TileLoader":
    """Permite usar el loader con ``with``."""
    return self

  def __exit__(self, *exc_info: object) -> None:
    """Cierra el pool al salir del ``with``."""
    self.close()

  def close(self) -> None:
    """Termina los procesos del pool."""
    if self._pool is not None:
      self._pool.close()
      self._pool.join()
      self._pool = None

  def load(self, root: str | Path) -> TileBatch:
    """Carga todas las teselas válidas de la carpeta ``root``."""
    relative_paths = list_batch_files(root)
    if not relative_paths:
      raise NoValidTilesError("no hay teselas válidas: el lote está vacío")
    absolute_paths = [str(Path(root) / path) for path in relative_paths]
    tiles, errors = self._decode_all(absolute_paths)
    return self._compact(tiles, relative_paths, errors)

  def _ensure_pool(self):
    """Crea el pool ``spawn`` si todavía no existe."""
    if self._pool is None:
      self._pool = multiprocessing.get_context(START_METHOD).Pool(self.workers)
    return self._pool

  def _decode_all(self, paths: list[str]) -> tuple[np.ndarray, dict[int, str]]:
    """Decodifica en paralelo sobre un bloque compartido y devuelve una copia."""
    n_tiles = len(paths)
    block = shared_memory.SharedMemory(create=True, size=n_tiles * int(np.prod(TILE_SHAPE)))
    try:
      tasks = [(path, index, block.name, n_tiles) for index, path in enumerate(paths)]
      results = self._ensure_pool().imap_unordered(decode_into_shared, tasks, DECODE_CHUNKSIZE)
      errors = {index: error for index, error in results if error is not None}
      tiles = np.ndarray((n_tiles, *TILE_SHAPE), dtype=np.uint8, buffer=block.buf).copy()
    finally:
      block.close()
      block.unlink()
    return tiles, errors

  @staticmethod
  def _compact(tiles: np.ndarray, paths: list[str], errors: dict[int, str]) -> TileBatch:
    """Quita las teselas inválidas conservando el orden de las válidas."""
    valid = [index for index in range(len(paths)) if index not in errors]
    if not valid:
      raise NoValidTilesError("no hay teselas válidas: ningún archivo del lote se pudo decodificar")
    skipped = tuple(paths[index] for index in sorted(errors))
    compacted = tiles if not errors else tiles[valid]
    return TileBatch(compacted, tuple(paths[index] for index in valid), skipped)
