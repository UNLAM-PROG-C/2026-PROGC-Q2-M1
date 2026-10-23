"""Estado del worker y del trabajo en el proceso web (design D5).

``JobManager`` mantiene ``idle | running(job_id, snapshot)``. Iniciar un
trabajo pasa por un ``asyncio.Lock``: dos ``POST /api/jobs`` simultáneos no
pueden ver los dos "sin trabajo en curso" (el segundo recibe 409). El snapshot
(última etapa y fracción, carga y resultados parciales) se actualiza con cada
evento del worker y permite recuperar el estado al recargar la página.

``handle()`` traduce cada evento del worker a los eventos JSON que se
retransmiten por WebSocket; se llama siempre desde el hilo del event loop.
"""

import asyncio
import dataclasses
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from app.core.params import InvalidParamsError, MosaicParams, derive_rows
from app.core.result import StageTimings
from app.web.execution import ExecutionModeError, backends_for_mode, effective_k
from app.web.rules import MAX_SEED
from app.web.uploads import UploadGoneError, UploadStore
from app.worker.messages import (
  BackendFinished,
  JobFailed,
  JobFinished,
  JobProgress,
  JobRejected,
  LoadFinished,
  RunJob,
  WorkerCrashed,
  WorkerReady,
)

STATUS_RUNNING, STATUS_FINISHED, STATUS_FAILED = "running", "finished", "failed"
JOB_CONFLICT_REASON = "ya hay un trabajo en curso"
WORKER_CRASHED_REASON = "el worker se detuvo inesperadamente"
WORKER_RESTARTING = f"{WORKER_CRASHED_REASON}; se está reiniciando"
HTTP_BAD_REQUEST, HTTP_NOT_FOUND, HTTP_CONFLICT, HTTP_UNAVAILABLE = 400, 404, 409, 503
RESULT_KINDS = ("preview", "png", "jpg")

logger = logging.getLogger(__name__)


class JobRequestError(Exception):
  """Pedido de trabajo rechazado; ``status_code`` es el código HTTP."""

  def __init__(self, status_code: int, message: str) -> None:
    """Guarda el código y el motivo legible."""
    super().__init__(message)
    self.status_code = status_code


@dataclass(frozen=True)
class JobRequest:
  """Cuerpo de ``POST /api/jobs``."""

  tiles_id: str
  target_id: str
  cols: int
  tile_px: int
  alpha: float
  seed: int
  mode: str


@dataclass
class JobSnapshot:
  """Trabajo en curso o último trabajo terminado."""

  job_id: str
  mode: str
  backends: tuple[str, ...]
  tiles_id: str
  target_id: str
  params: MosaicParams
  status: str = STATUS_RUNNING
  progress: dict | None = None
  load: dict | None = None
  results: dict[str, BackendFinished] = field(default_factory=dict)
  error: str | None = None

  def to_json(self) -> dict:
    """``JobSnapshot`` del frontend."""
    params = {name: getattr(self.params, name) for name in ("cols", "tile_px", "alpha", "seed", "k")}
    return {
      "job_id": self.job_id,
      "status": self.status,
      "mode": self.mode,
      "backends": list(self.backends),
      "tiles_id": self.tiles_id,
      "target_id": self.target_id,
      "params": params,
      "progress": self.progress,
      "load": self.load,
      "results": [result_json(result) for result in self.results.values()],
      "error": self.error,
    }


def timings_json(timings: StageTimings) -> dict:
  """Tiempos en ms como números de Python (``None`` = no aplica)."""
  return {name: None if value is None else float(value) for name, value in dataclasses.asdict(timings).items()}


def result_json(result: BackendFinished) -> dict:
  """``BackendResult`` del frontend (sin rutas del disco)."""
  return {
    "backend": result.backend,
    "device": result.device,
    "timings": timings_json(result.timings),
    "init_ms": result.init_ms,
    "width": result.width,
    "height": result.height,
  }


def load_json(load: LoadFinished) -> dict:
  """``LoadInfo`` del frontend."""
  fields = ("load_ms", "reused", "n_tiles", "skipped_files", "rows", "cols", "m_cells")
  return {name: getattr(load, name) for name in fields}


class JobManager:
  """Un trabajo a la vez, su snapshot y el estado del worker."""

  def __init__(self, store: UploadStore, send: Callable[[RunJob], None], max_output_pixels: int) -> None:
    """``send`` entrega la orden al worker (``WorkerClient.send``)."""
    self._store, self._send, self._max_output_pixels = store, send, max_output_pixels
    self._lock = asyncio.Lock()
    self.ready: WorkerReady | None = None
    self.worker_error: str | None = None
    self.snapshot: JobSnapshot | None = None

  @property
  def running(self) -> bool:
    """Hay un trabajo en curso."""
    return self.snapshot is not None and self.snapshot.status == STATUS_RUNNING

  def worker_json(self) -> dict:
    """``WorkerInfo`` del frontend."""
    return {"ready": self.ready is not None, "error": self.worker_error}

  async def start(self, request: JobRequest) -> JobSnapshot:
    """Valida, prepara la carpeta de resultados y envía ``RunJob`` al worker."""
    async with self._lock:
      if self.running:
        raise JobRequestError(HTTP_CONFLICT, JOB_CONFLICT_REASON)
      snapshot = self._build_snapshot(request)
      output_dir = await self._reserve(snapshot)
      try:
        self._dispatch(snapshot, output_dir)
      except JobRequestError:
        self._store.release()
        raise
      self.snapshot = snapshot
      return snapshot

  async def _reserve(self, snapshot: JobSnapshot) -> Path:
    """Reserva las subidas del trabajo en el almacén y crea su carpeta de resultados."""
    try:
      return await run_in_threadpool(self._store.create_job_dir, snapshot.job_id, snapshot.tiles_id, snapshot.target_id)
    except UploadGoneError as error:
      raise JobRequestError(HTTP_NOT_FOUND, f"{error} ya no está disponible: volvé a subirlo") from error

  def _build_snapshot(self, request: JobRequest) -> JobSnapshot:
    """Valida el pedido completo y arma el snapshot del trabajo nuevo."""
    tiles, target = self._store.tiles(request.tiles_id), self._store.target(request.target_id)
    if tiles is None or target is None:
      missing = "el lote" if tiles is None else "la imagen objetivo"
      raise JobRequestError(HTTP_NOT_FOUND, f"{missing} ya no está disponible: volvé a subirlo")
    try:
      backends = backends_for_mode(request.mode, self.ready)
      params = self._params(request, effective_k(tiles.accepted))
    except (ExecutionModeError, InvalidParamsError) as error:
      raise JobRequestError(HTTP_BAD_REQUEST, str(error)) from error
    self._check_output_size(params, target.width, target.height)
    job_id = uuid.uuid4().hex
    return JobSnapshot(job_id, request.mode, backends, request.tiles_id, request.target_id, params)

  @staticmethod
  def _params(request: JobRequest, k: int) -> MosaicParams:
    """Parámetros validados por el núcleo, más el máximo de semilla de la interfaz."""
    if isinstance(request.seed, int) and request.seed > MAX_SEED:
      raise InvalidParamsError(f"seed debe estar entre 0 y {MAX_SEED} (recibido: {request.seed})")
    return MosaicParams(cols=request.cols, tile_px=request.tile_px, k=k, alpha=request.alpha, seed=request.seed)

  def _check_output_size(self, params: MosaicParams, width: int, height: int) -> None:
    """Rechaza imágenes finales más grandes que el límite configurado."""
    rows = derive_rows(params.cols, width, height)
    out_width, out_height = params.cols * params.tile_px, rows * params.tile_px
    if out_width * out_height > self._max_output_pixels:
      raise JobRequestError(
        HTTP_BAD_REQUEST,
        f"la imagen final ({out_width} × {out_height} px) supera el límite de {self._max_output_pixels} píxeles",
      )

  def _dispatch(self, snapshot: JobSnapshot, output_dir: Path) -> None:
    """Envía la orden; si no hay worker vivo, el pedido falla con 503."""
    tiles = self._store.tiles(snapshot.tiles_id)
    target = self._store.target(snapshot.target_id)
    command = RunJob(
      snapshot.job_id,
      str(self._store.tiles_dir(tiles.tiles_id)),
      str(self._store.target_path(target)),
      snapshot.params,
      snapshot.backends,
      str(output_dir),
    )
    try:
      self._send(command)
    except RuntimeError as error:
      raise JobRequestError(HTTP_UNAVAILABLE, str(error)) from error

  def result_file(self, job_id: str, backend: str, kind: str) -> Path | None:
    """Archivo de un resultado del último trabajo, si existe."""
    snapshot = self.snapshot
    if snapshot is None or snapshot.job_id != job_id or backend not in snapshot.results:
      return None
    result = snapshot.results[backend]
    paths = {"preview": result.preview_path, "png": result.png_path, "jpg": result.jpeg_path}
    return Path(paths[kind]) if kind in paths else None

  # --- Eventos del worker -------------------------------------------------------

  def handle(self, event: object) -> list[dict]:
    """Actualiza el estado con un evento del worker y devuelve los eventos a retransmitir."""
    if isinstance(event, WorkerReady):
      self.ready, self.worker_error = event, None
      return [{"type": "worker_status", "worker": self.worker_json()}]
    if isinstance(event, WorkerCrashed):
      return self._on_crash()
    current = self.snapshot
    if current is None or getattr(event, "job_id", None) != current.job_id:
      logger.debug("evento de un trabajo que no es el actual: %r", event)
      return []
    return self._on_job_event(current, event)

  def _on_crash(self) -> list[dict]:
    """El worker murió: el trabajo en curso queda fallido y se espera el relanzamiento."""
    self.ready, self.worker_error = None, WORKER_RESTARTING
    events = []
    if self.running:
      events = self._on_job_event(self.snapshot, JobFailed(self.snapshot.job_id, WORKER_CRASHED_REASON))
    return [*events, {"type": "worker_status", "worker": self.worker_json()}]

  def _on_job_event(self, job: JobSnapshot, event: object) -> list[dict]:
    """Aplica un evento del trabajo actual a su snapshot."""
    base = {"job_id": job.job_id}
    if isinstance(event, JobProgress):
      job.progress = {"backend": event.backend, "stage": event.stage, "fraction": event.fraction}
      return [{"type": "job_progress", **base, **job.progress}]
    if isinstance(event, LoadFinished):
      job.load = load_json(event)
      return [{"type": "load_finished", **base, "load": job.load}]
    if isinstance(event, BackendFinished):
      job.results[event.backend] = event
      return [{"type": "backend_finished", **base, "result": result_json(event)}]
    if isinstance(event, JobFinished):
      job.status = STATUS_FINISHED
      self._store.release()
      return [{"type": "job_finished", **base}]
    if isinstance(event, JobFailed | JobRejected):
      job.status, job.error = STATUS_FAILED, event.reason
      self._store.release()
      return [{"type": "job_failed", **base, "reason": event.reason}]
    return []
