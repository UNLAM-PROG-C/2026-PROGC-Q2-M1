"""Aplicación FastAPI del proceso web (design D1 y D5).

``create_app()`` arma los componentes y el *lifespan*:

- al arrancar: vacía el directorio temporal, arranca el ``ProgressHub`` y lanza
  el worker con ``WorkerClient`` (que crea el proceso con ``spawn``);
- al apagar: ``WorkerClient.stop()`` (``Shutdown`` → ``join`` → ``terminate``),
  detiene el hub y borra subidas y resultados.

Los eventos del worker llegan por los hilos de ``WorkerClient``; se pasan al
event loop con ``call_soon_threadsafe`` para que el estado (``JobManager``) se
toque siempre desde un único hilo.

El proceso web no hace cómputo: no decodifica imágenes, no ejecuta backends ni
crea contextos de GPU. Tampoco sirve archivos del frontend.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.web.execution import execution_options
from app.web.hub import ProgressHub
from app.web.jobs import JobManager, JobRequestError
from app.web.routes import register_routes
from app.web.rules import rules_json
from app.web.schemas import status_json, target_json, tiles_json
from app.web.uploads import UploadError, UploadStore
from app.web.worker_client import EventCallback, WorkerClient
from app.worker.main import WorkerOptions
from app.worker.messages import Command, WorkerCrashed, WorkerReady

logger = logging.getLogger(__name__)


class WorkerLike(Protocol):
  """Lo que el proceso web usa del worker (``WorkerClient`` o un falso en los tests)."""

  def start(self) -> None:
    """Lanza el worker."""

  def send(self, command: Command) -> None:
    """Encola una orden."""

  def stop(self) -> None:
    """Apagado ordenado."""


WorkerFactory = Callable[[EventCallback], WorkerLike]


class AppContext:
  """Componentes del proceso web compartidos por las rutas."""

  def __init__(self, settings: Settings, worker_factory: WorkerFactory) -> None:
    """Crea el almacén de subidas, el hub y el gestor de trabajos (el worker se lanza en el lifespan)."""
    self.settings = settings
    self.store = UploadStore(
      settings.temp_dir, settings.max_upload_bytes, settings.max_zip_entries, settings.tile_sample_count
    )
    self.hub = ProgressHub()
    self.jobs = JobManager(self.store, self._send, settings.max_output_pixels)
    self._worker_factory = worker_factory
    self.worker: WorkerLike | None = None

  def _send(self, command: Command) -> None:
    """Entrega una orden al worker actual."""
    if self.worker is None:
      raise RuntimeError("el worker no está en ejecución")
    self.worker.send(command)

  def state_json(self) -> dict:
    """``AppState`` del frontend (``GET /api/state`` y snapshot del WebSocket)."""
    ready = self.jobs.ready
    snapshot = self.jobs.snapshot
    return {
      "worker": self.jobs.worker_json(),
      "backends": [status_json(status) for status in ready.statuses] if ready else [],
      "execution": execution_options(ready),
      "calibration": vars(ready.calibration) if ready and ready.calibration else None,
      "rules": rules_json(self.settings),
      "job": snapshot.to_json() if snapshot else None,
      "last_tiles": tiles_json(self.store.last_tiles),
      "last_target": target_json(self.store.last_target),
    }

  def on_worker_event(self, event: object) -> None:
    """Aplica un evento del worker (en el event loop) y lo retransmite."""
    for message in self.jobs.handle(event):
      self.hub.publish(message)
    if isinstance(event, WorkerReady | WorkerCrashed):
      self.hub.publish({"type": "state", "state": self.state_json()})

  async def startup(self) -> None:
    """Directorio temporal limpio, hub y worker."""
    loop = asyncio.get_running_loop()
    await run_in_threadpool(self.store.reset)
    self.hub.start()
    self.worker = self._worker_factory(lambda event: _call_in_loop(loop, self.on_worker_event, event))
    await run_in_threadpool(self.worker.start)

  async def shutdown(self) -> None:
    """Apaga el worker, el hub y borra los temporales."""
    if self.worker is not None:
      await run_in_threadpool(self.worker.stop)
    await self.hub.stop()
    await run_in_threadpool(self.store.cleanup)


def _call_in_loop(loop: asyncio.AbstractEventLoop, callback: Callable[[object], None], event: object) -> None:
  """Pasa un evento de un hilo del cliente al event loop (si sigue abierto)."""
  with contextlib.suppress(RuntimeError):
    loop.call_soon_threadsafe(callback, event)


def default_worker_factory(settings: Settings) -> WorkerFactory:
  """Fábrica del ``WorkerClient`` real con la configuración dada."""
  options = WorkerOptions(decode_processes=settings.decode_processes, preview_max_side=settings.preview_max_side)
  return lambda on_event: WorkerClient(on_event, options, settings.shutdown_timeout_s)


def create_app(settings: Settings, worker_factory: WorkerFactory | None = None) -> FastAPI:
  """Arma la aplicación; ``worker_factory`` reemplaza al worker real en los tests."""
  context = AppContext(settings, worker_factory or default_worker_factory(settings))

  @asynccontextmanager
  async def lifespan(_app: FastAPI):
    await context.startup()
    try:
      yield
    finally:
      await context.shutdown()

  app = FastAPI(title="Fotomosaico", lifespan=lifespan)
  app.state.context = context
  app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_methods=["*"], allow_headers=["*"])
  app.add_exception_handler(UploadError, _error_response)
  app.add_exception_handler(JobRequestError, _error_response)
  register_routes(app, context)
  return app


async def _error_response(_request, error: Exception) -> JSONResponse:
  """Errores propios → ``{detail: motivo}`` con su código HTTP."""
  return JSONResponse({"detail": str(error)}, status_code=error.status_code)
