"""Subidas del lote y del objetivo como recursos separados (design D7).

Estructura en el directorio temporal::

    <MOSAIC_TEMP_DIR>/tiles/<tiles_id>/...      lote (archivos sueltos o zip extraído)
    <MOSAIC_TEMP_DIR>/targets/<target_id>/...   imagen objetivo
    <MOSAIC_TEMP_DIR>/jobs/<job_id>/<backend>/  resultados (los escribe el worker)

- Se escribe por bloques con un presupuesto de bytes: nunca se carga un archivo
  entero en memoria y se corta apenas se supera el límite (413).
- Solo se aceptan JPEG, PNG y WebP por extensión; el resto se ignora y se cuenta.
- El zip se extrae entrada por entrada: se rechazan rutas absolutas o que salgan
  del directorio (``Path.resolve()``) y enlaces simbólicos, y se cortan el tamaño
  descomprimido y la cantidad de entradas.
- Retención: el último lote, el último objetivo, los que use un trabajo en curso
  y los resultados del último trabajo. Lo demás se borra al recibir una subida
  nueva o al empezar un trabajo.
- Las subidas en uso las registra el propio almacén al crear la carpeta del
  trabajo, bajo el mismo lock con el que borra. Así una subida que termina en el
  threadpool justo cuando otra pestaña lanza un trabajo nunca borra el lote que
  ese trabajo va a leer: o el borrado ocurre antes y el trabajo se rechaza con
  404, o el trabajo se registra antes y su lote se conserva.

El proceso web no decodifica imágenes: del objetivo lee solo la cabecera (tamaño
y orientación EXIF) para informar sus dimensiones.
"""

import logging
import shutil
import stat
import threading
import uuid
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import BinaryIO

from PIL import Image, UnidentifiedImageError

from app.config import BYTES_PER_MB
from app.core.constants import SUPPORTED_IMAGE_FORMATS

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
ACCEPTED_FORMATS_TEXT = "JPEG, PNG o WebP"
COPY_CHUNK_BYTES = 1024 * 1024
MACOS_METADATA_DIR = "__MACOSX"
APPLE_DOUBLE_PREFIX = "._"
TILES_DIR, TARGETS_DIR, JOBS_DIR = "tiles", "targets", "jobs"
ZIP_SUFFIX = ".zip"
# Orientaciones EXIF que rotan 90° (el ancho y el alto se intercambian).
EXIF_ORIENTATION_TAG = 0x0112
TRANSPOSED_ORIENTATIONS = frozenset({5, 6, 7, 8})
HTTP_BAD_REQUEST = 400
HTTP_TOO_LARGE = 413

logger = logging.getLogger(__name__)


class UploadError(Exception):
  """Subida rechazada; ``status_code`` es el código HTTP a responder."""

  status_code = HTTP_BAD_REQUEST


class UploadTooLargeError(UploadError):
  """La subida (o lo descomprimido) supera el límite configurado."""

  status_code = HTTP_TOO_LARGE


class UploadGoneError(Exception):
  """Una subida que pidió un trabajo se borró antes de que el trabajo la reservara."""


@dataclass(frozen=True)
class TilesSummary:
  """Resumen de un lote; ``samples`` son rutas relativas de una muestra acotada."""

  tiles_id: str
  accepted: int
  ignored: int
  rejected: int
  samples: tuple[str, ...]


@dataclass(frozen=True)
class TargetSummary:
  """Imagen objetivo subida; ``filename`` es el nombre guardado dentro de su carpeta."""

  target_id: str
  filename: str
  width: int
  height: int


@dataclass
class _Counts:
  """Archivos aceptados (rutas relativas), ignorados y rechazados de una subida."""

  accepted: list[str]
  ignored: int = 0
  rejected: int = 0


class ByteBudget:
  """Bytes que todavía se pueden escribir en una subida."""

  def __init__(self, limit_bytes: int) -> None:
    """Arranca con el límite completo."""
    self.limit_bytes = limit_bytes
    self._remaining = limit_bytes

  def consume(self, size: int) -> None:
    """Descuenta ``size`` bytes; si no alcanza, rechaza la subida."""
    self._remaining -= size
    if self._remaining < 0:
      raise UploadTooLargeError(f"la subida supera el límite de {self.limit_bytes // BYTES_PER_MB} MB")


def copy_limited(source: BinaryIO, destination: Path, budget: ByteBudget) -> None:
  """Copia por bloques respetando el presupuesto."""
  destination.parent.mkdir(parents=True, exist_ok=True)
  with destination.open("wb") as output:
    while chunk := source.read(COPY_CHUNK_BYTES):
      budget.consume(len(chunk))
      output.write(chunk)


def has_image_extension(name: str) -> bool:
  """JPEG, PNG o WebP según la extensión, sin distinguir mayúsculas."""
  return PurePosixPath(name).suffix.lower() in IMAGE_EXTENSIONS


def is_macos_metadata(name: str) -> bool:
  """Archivos que agrega el compresor de macOS (``__MACOSX/``, ``._*``)."""
  parts = PurePosixPath(name).parts
  return MACOS_METADATA_DIR in parts or (bool(parts) and parts[-1].startswith(APPLE_DOUBLE_PREFIX))


def safe_destination(root: Path, name: str) -> Path | None:
  """Destino de ``name`` dentro de ``root``, o ``None`` si es absoluto o se escapa."""
  if not name or name.startswith("/") or PureWindowsPath(name).drive or PureWindowsPath(name).root:
    return None
  destination = (root / name).resolve()
  return destination if destination.is_relative_to(root.resolve()) and destination != root.resolve() else None


def is_zip_symlink(info: zipfile.ZipInfo) -> bool:
  """La entrada del zip es un enlace simbólico (permisos Unix en ``external_attr``)."""
  return stat.S_ISLNK(info.external_attr >> 16)


def _remove(path: Path) -> None:
  """Borra una carpeta; en Windows puede fallar si se está sirviendo un archivo."""
  shutil.rmtree(path, ignore_errors=True)


def _new_id() -> str:
  """Identificador opaco de una subida o un trabajo."""
  return uuid.uuid4().hex


class UploadStore:
  """Guarda subidas y directorios de trabajos, y aplica la retención."""

  def __init__(self, root: Path, max_bytes: int, max_entries: int, sample_count: int) -> None:
    """``root`` es el directorio temporal base."""
    self.root = root.resolve()
    self._max_bytes, self._max_entries, self._sample_count = max_bytes, max_entries, sample_count
    self._lock = threading.Lock()
    self._tiles: dict[str, TilesSummary] = {}
    self._targets: dict[str, TargetSummary] = {}
    self.last_tiles: TilesSummary | None = None
    self.last_target: TargetSummary | None = None
    # Subidas del trabajo en curso. Se lee con el lock tomado; ``release()`` la
    # reemplaza sin lock (asignar una referencia es atómico) para no bloquear el
    # event loop mientras otro hilo borra archivos.
    self._in_use: frozenset[str] = frozenset()

  # --- Ciclo de vida ------------------------------------------------------------

  def reset(self) -> None:
    """Borra lo que haya quedado (también de ejecuciones anteriores) y recrea las carpetas."""
    with self._lock:
      for name in (TILES_DIR, TARGETS_DIR, JOBS_DIR):
        _remove(self.root / name)
        (self.root / name).mkdir(parents=True, exist_ok=True)
      self._tiles.clear()
      self._targets.clear()
      self.last_tiles = self.last_target = None
      self._in_use = frozenset()

  def cleanup(self) -> None:
    """Al apagar: borra subidas y resultados (solo las carpetas propias)."""
    for name in (TILES_DIR, TARGETS_DIR, JOBS_DIR):
      _remove(self.root / name)

  # --- Lote ---------------------------------------------------------------------

  def save_tiles_files(self, files: Iterable[tuple[str, BinaryIO]]) -> TilesSummary:
    """Lote como archivos sueltos: ``(nombre, contenido)``."""
    tiles_id = _new_id()
    folder = self.root / TILES_DIR / tiles_id
    return self._finish_tiles(tiles_id, folder, lambda: self._write_files(folder, list(files)))

  def save_tiles_zip(self, source: BinaryIO) -> TilesSummary:
    """Lote como un único zip, que se extrae de forma segura."""
    tiles_id = _new_id()
    folder = self.root / TILES_DIR / tiles_id
    return self._finish_tiles(tiles_id, folder, lambda: self._extract_zip(folder, source))

  def _finish_tiles(self, tiles_id: str, folder: Path, write) -> TilesSummary:
    """Escribe el lote, valida que haya imágenes y lo registra como el último."""
    folder.mkdir(parents=True)
    try:
      counts = write()
      if not counts.accepted:
        raise UploadError(f"el lote no tiene imágenes {ACCEPTED_FORMATS_TEXT}")
    except BaseException:
      _remove(folder)
      raise
    samples = tuple(sorted(counts.accepted)[: self._sample_count])
    summary = TilesSummary(tiles_id, len(counts.accepted), counts.ignored, counts.rejected, samples)
    with self._lock:
      self._tiles[tiles_id] = self.last_tiles = summary
      self._prune(TILES_DIR, self._tiles, {tiles_id, *self._in_use})
    return summary

  def _write_files(self, folder: Path, files: list[tuple[str, BinaryIO]]) -> _Counts:
    """Guarda los archivos sueltos admitidos (por nombre base, sin carpetas)."""
    self._check_entries(len(files))
    counts, budget = _Counts([]), ByteBudget(self._max_bytes)
    for index, (raw_name, source) in enumerate(files):
      name = PurePosixPath(raw_name.replace("\\", "/")).name
      if is_macos_metadata(name) or not has_image_extension(name):
        counts.ignored += 1
        continue
      destination = safe_destination(folder, name)
      if destination is None:
        counts.rejected += 1
        continue
      if destination.exists():
        destination = folder / f"{index}_{name}"
      copy_limited(source, destination, budget)
      counts.accepted.append(destination.relative_to(folder).as_posix())
    return counts

  def _extract_zip(self, folder: Path, source: BinaryIO) -> _Counts:
    """Copia el zip (al lado de la carpeta del lote) con límite, lo extrae entrada por entrada y lo borra."""
    archive_path = folder.with_suffix(ZIP_SUFFIX)
    try:
      copy_limited(source, archive_path, ByteBudget(self._max_bytes))
      with zipfile.ZipFile(archive_path) as archive:
        return self._extract_entries(folder, archive)
    except zipfile.BadZipFile as error:
      raise UploadError("el archivo no es un zip válido") from error
    finally:
      archive_path.unlink(missing_ok=True)

  def _extract_entries(self, folder: Path, archive: zipfile.ZipFile) -> _Counts:
    """Clasifica y extrae cada entrada respetando el tamaño descomprimido."""
    entries = [info for info in archive.infolist() if not info.is_dir()]
    self._check_entries(len(entries))
    counts, budget = _Counts([]), ByteBudget(self._max_bytes)
    for info in entries:
      name = info.filename.replace("\\", "/")
      destination = None if is_zip_symlink(info) else safe_destination(folder, name)
      if destination is None:
        counts.rejected += 1
      elif is_macos_metadata(name) or not has_image_extension(name):
        counts.ignored += 1
      else:
        with archive.open(info) as entry:
          copy_limited(entry, destination, budget)
        counts.accepted.append(destination.relative_to(folder).as_posix())
    return counts

  def _check_entries(self, count: int) -> None:
    """Corta lotes con más archivos que el máximo configurado."""
    if count > self._max_entries:
      raise UploadTooLargeError(f"el lote supera el máximo de {self._max_entries} archivos")

  # --- Objetivo -----------------------------------------------------------------

  def save_target(self, raw_name: str, source: BinaryIO) -> TargetSummary:
    """Guarda la imagen objetivo y lee sus dimensiones de la cabecera."""
    name = PurePosixPath((raw_name or "").replace("\\", "/")).name
    if not has_image_extension(name) or is_macos_metadata(name):
      raise UploadError(f"formato de imagen objetivo no admitido: usá {ACCEPTED_FORMATS_TEXT}")
    target_id = _new_id()
    folder = self.root / TARGETS_DIR / target_id
    folder.mkdir(parents=True)
    try:
      copy_limited(source, folder / name, ByteBudget(self._max_bytes))
      width, height = read_dimensions(folder / name)
    except BaseException:
      _remove(folder)
      raise
    summary = TargetSummary(target_id, name, width, height)
    with self._lock:
      self._targets[target_id] = self.last_target = summary
      self._prune(TARGETS_DIR, self._targets, {target_id, *self._in_use})
    return summary

  # --- Consultas ----------------------------------------------------------------

  def tiles(self, tiles_id: str) -> TilesSummary | None:
    """Resumen de un lote conservado."""
    return self._tiles.get(tiles_id)

  def target(self, target_id: str) -> TargetSummary | None:
    """Objetivo conservado."""
    return self._targets.get(target_id)

  def tiles_dir(self, tiles_id: str) -> Path:
    """Carpeta del lote (el worker la lee por ruta)."""
    return self.root / TILES_DIR / tiles_id

  def target_path(self, summary: TargetSummary) -> Path:
    """Archivo del objetivo."""
    return self.root / TARGETS_DIR / summary.target_id / summary.filename

  def sample_path(self, summary: TilesSummary, index: int) -> Path | None:
    """Archivo original de la muestra ``index`` del lote, o ``None`` si no existe."""
    if not 0 <= index < len(summary.samples):
      return None
    return self.tiles_dir(summary.tiles_id) / summary.samples[index]

  # --- Trabajos y retención -----------------------------------------------------

  def create_job_dir(self, job_id: str, tiles_id: str, target_id: str) -> Path:
    """Reserva las subidas del trabajo nuevo y crea su carpeta de resultados.

    Borra los resultados anteriores y lo no retenido. Lanza ``UploadGoneError``
    si una subida pedida ya se borró (la reserva y el borrado comparten el lock).
    """
    with self._lock:
      if tiles_id not in self._tiles or target_id not in self._targets:
        raise UploadGoneError("el lote" if tiles_id not in self._tiles else "la imagen objetivo")
      self._in_use = frozenset((tiles_id, target_id))
      for folder in (self.root / JOBS_DIR).iterdir():
        _remove(folder)
      self._prune(TILES_DIR, self._tiles, {*self._in_use, *self._last_ids()})
      self._prune(TARGETS_DIR, self._targets, {*self._in_use, *self._last_ids()})
    folder = self.root / JOBS_DIR / job_id
    folder.mkdir(parents=True)
    return folder

  def release(self) -> None:
    """El trabajo en curso terminó: sus subidas vuelven a la retención normal."""
    self._in_use = frozenset()

  def _last_ids(self) -> set[str]:
    """Ids del último lote y el último objetivo."""
    return {
      summary_id for summary_id in (self._last_id(self.last_tiles), self._last_id(self.last_target)) if summary_id
    }

  @staticmethod
  def _last_id(summary: TilesSummary | TargetSummary | None) -> str | None:
    """Id de un resumen, si hay."""
    if summary is None:
      return None
    return summary.tiles_id if isinstance(summary, TilesSummary) else summary.target_id

  def _prune(self, kind: str, registry: dict, keep: set[str]) -> None:
    """Borra las subidas de un tipo que no estén en ``keep`` (con el lock tomado)."""
    for upload_id in [upload_id for upload_id in registry if upload_id not in keep]:
      del registry[upload_id]
      _remove(self.root / kind / upload_id)


def read_dimensions(path: Path) -> tuple[int, int]:
  """Ancho y alto ya orientados, leyendo solo la cabecera (no decodifica los píxeles)."""
  try:
    with Image.open(path) as image:
      if image.format not in SUPPORTED_IMAGE_FORMATS:
        raise UploadError(f"formato de imagen objetivo no admitido: usá {ACCEPTED_FORMATS_TEXT}")
      width, height = image.size
      orientation = image.getexif().get(EXIF_ORIENTATION_TAG)
  except (UnidentifiedImageError, OSError) as error:
    raise UploadError("no se pudo leer la imagen objetivo") from error
  return (height, width) if orientation in TRANSPOSED_ORIENTATIONS else (width, height)
