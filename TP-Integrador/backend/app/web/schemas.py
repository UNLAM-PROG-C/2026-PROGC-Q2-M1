"""Conversión de los resúmenes del backend al JSON que espera el frontend.

Los nombres de los campos son los de ``frontend/src/api/types.ts`` (snake_case):
ese archivo es el contrato entre ambos lados.
"""

from app.backends.registry import BackendStatus
from app.web.uploads import TargetSummary, TilesSummary


def tiles_json(summary: TilesSummary | None) -> dict | None:
  """``TilesSummary`` del frontend."""
  if summary is None:
    return None
  return {
    "tiles_id": summary.tiles_id,
    "accepted": summary.accepted,
    "ignored": summary.ignored,
    "rejected": summary.rejected,
    "samples": list(summary.samples),
  }


def target_json(summary: TargetSummary | None) -> dict | None:
  """``TargetSummary`` del frontend."""
  if summary is None:
    return None
  return {
    "target_id": summary.target_id,
    "filename": summary.filename,
    "width": summary.width,
    "height": summary.height,
  }


def status_json(status: BackendStatus) -> dict:
  """``BackendStatus`` del frontend."""
  return {
    "name": status.name,
    "available": status.available,
    "device_name": status.device_name,
    "reason": status.reason,
    "init_ms": status.init_ms,
    "warnings": list(status.warnings),
  }
