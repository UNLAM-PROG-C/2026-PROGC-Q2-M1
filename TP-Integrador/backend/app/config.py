"""Configuración del proceso web y del worker (design D10).

Cada valor sale de una variable de entorno ``MOSAIC_*`` con un valor por
defecto. ``load_env_file()`` carga además un ``backend/.env`` local opcional
(con ``python-dotenv``) sin pisar las variables que ya estén exportadas; hay que
llamarla antes de lanzar el worker para que este herede también las variables
de los backends GPU (ver ``env.example``).
"""

import os
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Valores por defecto. El origen coincide con FRONTEND_PORT del frontend.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_FRONTEND_ORIGIN = "http://127.0.0.1:5173"
DEFAULT_TEMP_SUBDIR = "fotomosaico"
DEFAULT_MAX_UPLOAD_MB = 2048
DEFAULT_MAX_ZIP_ENTRIES = 20000
# 150 megapíxeles (450 MB sin comprimir): admite el mosaico de 12.800 × 9.600 de la spec.
DEFAULT_MAX_OUTPUT_PIXELS = 150_000_000
DEFAULT_PREVIEW_MAX_SIDE = 2048
DEFAULT_TILE_SAMPLE_COUNT = 12
DEFAULT_CPU_CONFIRM_SECONDS = 60.0
# 0 significa "un proceso de decodificación por núcleo".
DEFAULT_DECODE_PROCESSES = 0
DEFAULT_SHUTDOWN_TIMEOUT_S = 15.0

BYTES_PER_MB = 1024 * 1024
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


@dataclass(frozen=True)
class Settings:
  """Configuración ya resuelta; se pasa explícitamente a quien la necesita."""

  host: str = DEFAULT_HOST
  port: int = DEFAULT_PORT
  frontend_origin: str = DEFAULT_FRONTEND_ORIGIN
  temp_dir: Path = Path(tempfile.gettempdir()) / DEFAULT_TEMP_SUBDIR
  max_upload_mb: int = DEFAULT_MAX_UPLOAD_MB
  max_zip_entries: int = DEFAULT_MAX_ZIP_ENTRIES
  max_output_pixels: int = DEFAULT_MAX_OUTPUT_PIXELS
  preview_max_side: int = DEFAULT_PREVIEW_MAX_SIDE
  tile_sample_count: int = DEFAULT_TILE_SAMPLE_COUNT
  cpu_confirm_seconds: float = DEFAULT_CPU_CONFIRM_SECONDS
  decode_processes: int = DEFAULT_DECODE_PROCESSES
  shutdown_timeout_s: float = DEFAULT_SHUTDOWN_TIMEOUT_S

  @property
  def max_upload_bytes(self) -> int:
    """Límite de bytes de una subida (y de lo descomprimido de un zip)."""
    return self.max_upload_mb * BYTES_PER_MB


# Variable de entorno → (campo de Settings, conversión).
_FIELDS: dict[str, tuple[str, Callable[[str], object]]] = {
  "MOSAIC_HOST": ("host", str),
  "MOSAIC_PORT": ("port", int),
  "MOSAIC_FRONTEND_ORIGIN": ("frontend_origin", lambda value: value.rstrip("/")),
  "MOSAIC_TEMP_DIR": ("temp_dir", Path),
  "MOSAIC_MAX_UPLOAD_MB": ("max_upload_mb", int),
  "MOSAIC_MAX_ZIP_ENTRIES": ("max_zip_entries", int),
  "MOSAIC_MAX_OUTPUT_PIXELS": ("max_output_pixels", int),
  "MOSAIC_PREVIEW_MAX_SIDE": ("preview_max_side", int),
  "MOSAIC_TILE_SAMPLE_COUNT": ("tile_sample_count", int),
  "MOSAIC_CPU_CONFIRM_SECONDS": ("cpu_confirm_seconds", float),
  "MOSAIC_DECODE_PROCESSES": ("decode_processes", int),
  "MOSAIC_SHUTDOWN_TIMEOUT_S": ("shutdown_timeout_s", float),
}


def load_env_file(path: Path = ENV_FILE) -> None:
  """Carga ``backend/.env`` si existe; las variables ya exportadas tienen prioridad."""
  if path.is_file():
    load_dotenv(path, override=False)


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
  """Arma la configuración con las variables definidas (vacías = valor por defecto)."""
  source = os.environ if environ is None else environ
  values = {}
  for name, (field, convert) in _FIELDS.items():
    raw = source.get(name, "").strip()
    if raw:
      values[field] = convert(raw)
  return Settings(**values)
