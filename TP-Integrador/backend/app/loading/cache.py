"""Reutilización de la última carga y medición del tiempo de la etapa común.

Se guarda solo la última carga (design D7): con N = 5.000 teselas, ``tiles_src``
ocupa unos 245 MB. La huella de un archivo es su ruta, su tamaño y su fecha de
modificación: alcanza para reconocer el mismo lote sin volver a leerlo.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.core.timing import elapsed_ms_since
from app.loading.target_loader import TargetImage, load_target
from app.loading.tile_loader import TileBatch, TileLoader, list_batch_files

FileFingerprint = tuple[str, int, int]
Fingerprint = tuple[str, tuple[FileFingerprint, ...]]
TargetLoaderFn = Callable[[str | Path, int], TargetImage]


def file_fingerprint(path: Path, name: str) -> FileFingerprint:
  """Huella de un archivo: nombre, tamaño y fecha de modificación."""
  stat = path.stat()
  return (name, stat.st_size, stat.st_mtime_ns)


def batch_fingerprint(root: str | Path) -> Fingerprint:
  """Huella de un lote: la carpeta y la huella de cada archivo, en orden."""
  base = Path(root).resolve()
  files = tuple(file_fingerprint(base / name, name) for name in list_batch_files(base))
  return (str(base), files)


@dataclass(frozen=True)
class LoadResult:
  """Resultado de la etapa común de carga."""

  tiles: TileBatch
  target: TargetImage
  tiles_ms: float
  target_ms: float
  tiles_reused: bool
  target_reused: bool

  @property
  def load_ms(self) -> float:
    """Tiempo total de la etapa común de carga."""
    return self.tiles_ms + self.target_ms

  @property
  def reused(self) -> bool:
    """Verdadero si no hubo que decodificar nada."""
    return self.tiles_reused and self.target_reused


class LoadCache:
  """Carga teselas y objetivo, reutilizando la última carga si coincide."""

  def __init__(self, tile_loader: TileLoader, target_loader: TargetLoaderFn = load_target) -> None:
    """Recibe el loader de teselas y la función que prepara el objetivo."""
    self._tile_loader = tile_loader
    self._target_loader = target_loader
    self._tiles_key: Fingerprint | None = None
    self._tiles: TileBatch | None = None
    self._target_key: tuple[FileFingerprint, int] | None = None
    self._target: TargetImage | None = None

  def load(self, tiles_root: str | Path, target_path: str | Path, cols: int) -> LoadResult:
    """Devuelve teselas y objetivo, decodificando solo lo que cambió."""
    tiles_start = time.perf_counter()
    tiles_reused = self._refresh_tiles(tiles_root)
    tiles_ms = elapsed_ms_since(tiles_start)
    target_start = time.perf_counter()
    target_reused = self._refresh_target(target_path, cols)
    target_ms = elapsed_ms_since(target_start)
    return LoadResult(self._tiles, self._target, tiles_ms, target_ms, tiles_reused, target_reused)

  def _refresh_tiles(self, root: str | Path) -> bool:
    """Recarga las teselas si el lote cambió; devuelve si se reutilizaron."""
    key = batch_fingerprint(root)
    if key == self._tiles_key:
      return True
    self._tiles = self._tile_loader.load(root)
    self._tiles_key = key
    return False

  def _refresh_target(self, path: str | Path, cols: int) -> bool:
    """Recarga el objetivo si cambió la imagen o ``cols``; devuelve si se reutilizó."""
    resolved = Path(path).resolve()
    key = (file_fingerprint(resolved, str(resolved)), cols)
    if key == self._target_key:
      return True
    self._target = self._target_loader(resolved, cols)
    self._target_key = key
    return False
