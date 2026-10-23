"""Rutas HTTP y WebSocket del proceso web (tabla de design D5).

Las rutas solo validan, guardan subidas (por bloques, en el *threadpool* para
no bloquear el event loop), envían órdenes al worker y sirven archivos tal
como están en disco.
"""

from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.config import BYTES_PER_MB
from app.web.jobs import RESULT_KINDS, JobRequest
from app.web.schemas import target_json, tiles_json
from app.web.uploads import UploadError, UploadTooLargeError

if TYPE_CHECKING:
  from app.web.api import AppContext

HTTP_NOT_FOUND = 404
# Código de cierre de WebSocket "policy violation" (origen no permitido).
WS_POLICY_VIOLATION = 1008
DOWNLOAD_EXTENSIONS = {"png": "png", "jpg": "jpg"}
NOT_FOUND = "no encontrado"


class JobBody(BaseModel):
  """Cuerpo JSON de ``POST /api/jobs``."""

  tiles_id: str
  target_id: str
  cols: int
  tile_px: int
  alpha: float
  seed: int
  mode: str


def _check_content_length(request: Request, max_bytes: int) -> None:
  """Corta antes de leer el cuerpo si el navegador ya anuncia que excede el límite."""
  declared = request.headers.get("content-length", "")
  if declared.isdigit() and int(declared) > max_bytes:
    raise UploadTooLargeError(f"la subida supera el límite de {max_bytes // BYTES_PER_MB} MB")


def _only_files(values: list) -> list[StarletteUploadFile]:
  """Partes del formulario que son archivos."""
  return [value for value in values if isinstance(value, StarletteUploadFile)]


def _file_or_404(path) -> FileResponse:
  """Sirve un archivo existente tal como está en disco."""
  if path is None or not path.is_file():
    raise HTTPException(HTTP_NOT_FOUND, NOT_FOUND)
  return FileResponse(path)


def register_routes(app: FastAPI, context: "AppContext") -> None:
  """Registra todas las rutas sobre ``app``."""
  _register_state_routes(app, context)
  _register_tiles_routes(app, context)
  _register_target_routes(app, context)
  _register_job_routes(app, context)


def _register_state_routes(app: FastAPI, context: "AppContext") -> None:
  """``GET /api/state`` y ``WS /ws``."""

  @app.get("/api/state")
  def get_state() -> dict:
    return context.state_json()

  @app.websocket("/ws")
  async def events(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    if origin is not None and origin.rstrip("/") != context.settings.frontend_origin:
      await websocket.close(code=WS_POLICY_VIOLATION)
      return
    await websocket.accept()
    context.hub.subscribe(websocket, {"type": "state", "state": context.state_json()})
    try:
      while True:
        await websocket.receive_text()
    except WebSocketDisconnect:
      pass
    finally:
      context.hub.unsubscribe(websocket)


def _register_tiles_routes(app: FastAPI, context: "AppContext") -> None:
  """Subida y consulta del lote."""
  settings, store = context.settings, context.store

  @app.post("/api/tiles")
  async def upload_tiles(request: Request) -> dict:
    _check_content_length(request, settings.max_upload_bytes)
    async with request.form(max_files=settings.max_zip_entries + 1, max_fields=settings.max_zip_entries + 1) as form:
      archive, files = _only_files(form.getlist("zip")), _only_files(form.getlist("files"))
      protected = context.jobs.protected_ids()
      if archive:
        summary = await run_in_threadpool(store.save_tiles_zip, archive[0].file, protected)
      elif files:
        summary = await run_in_threadpool(
          store.save_tiles_files, [(f.filename or "", f.file) for f in files], protected
        )
      else:
        raise UploadError("no se recibió ningún archivo: mandá un zip en 'zip' o imágenes en 'files'")
    return {
      "tiles_id": summary.tiles_id,
      "accepted": summary.accepted,
      "ignored": summary.ignored,
      "rejected": summary.rejected,
    }

  @app.get("/api/tiles/{tiles_id}")
  def get_tiles(tiles_id: str) -> dict:
    summary = store.tiles(tiles_id)
    if summary is None:
      raise HTTPException(HTTP_NOT_FOUND, "lote no encontrado")
    return tiles_json(summary)

  @app.get("/api/tiles/{tiles_id}/samples/{index}")
  def get_tile_sample(tiles_id: str, index: int) -> FileResponse:
    summary = store.tiles(tiles_id)
    return _file_or_404(store.sample_path(summary, index) if summary else None)


def _register_target_routes(app: FastAPI, context: "AppContext") -> None:
  """Subida y archivo de la imagen objetivo."""
  settings, store = context.settings, context.store

  @app.post("/api/targets")
  async def upload_target(request: Request) -> dict:
    _check_content_length(request, settings.max_upload_bytes)
    async with request.form() as form:
      files = _only_files(form.getlist("file"))
      if not files:
        raise UploadError("no se recibió la imagen objetivo en el campo 'file'")
      protected = context.jobs.protected_ids()
      summary = await run_in_threadpool(store.save_target, files[0].filename or "", files[0].file, protected)
    return target_json(summary)

  @app.get("/api/targets/{target_id}/image")
  def get_target_image(target_id: str) -> FileResponse:
    summary = store.target(target_id)
    return _file_or_404(store.target_path(summary) if summary else None)


def _register_job_routes(app: FastAPI, context: "AppContext") -> None:
  """Creación de trabajos y descarga de resultados."""

  @app.post("/api/jobs")
  async def create_job(body: JobBody) -> dict:
    snapshot = await context.jobs.start(JobRequest(**body.model_dump()))
    context.hub.publish({"type": "job_started", "job": snapshot.to_json()})
    return {"job_id": snapshot.job_id, "backends": list(snapshot.backends)}

  @app.get("/api/jobs/{job_id}/{backend}/{kind}")
  def get_result(job_id: str, backend: str, kind: str) -> FileResponse:
    if kind not in RESULT_KINDS:
      raise HTTPException(HTTP_NOT_FOUND, NOT_FOUND)
    path = context.jobs.result_file(job_id, backend, kind)
    if path is None or not path.is_file():
      raise HTTPException(HTTP_NOT_FOUND, NOT_FOUND)
    if kind in DOWNLOAD_EXTENSIONS:
      return FileResponse(path, filename=f"fotomosaico-{backend}.{DOWNLOAD_EXTENSIONS[kind]}")
    return FileResponse(path)
