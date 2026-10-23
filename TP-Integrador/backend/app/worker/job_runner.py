"""Ejecución de un trabajo dentro del worker (design D3).

``JobRunner.run()`` carga (con la cache de ``app/loading``), genera ``choice``
una sola vez, toma los backends pedidos con ``registry.resolve()`` y los
ejecuta en orden. El progreso de cada backend (Observer ``on_progress``) se
traduce en mensajes ``JobProgress`` con *throttling*. La imagen se guarda
después de que el backend devolvió el resultado, o sea fuera de la medición.
Cualquier error termina en un ``JobFailed`` con un motivo legible: el worker
sigue vivo y puede ejecutar el trabajo siguiente.
"""

import dataclasses
import logging
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

from app.backends.registry import BackendUnavailableError
from app.core.backend import MosaicBackend, OutOfMemoryError
from app.core.choice import generate_choice
from app.core.params import InvalidParamsError, MosaicParams
from app.loading.cache import LoadResult
from app.loading.target_loader import InvalidTargetError
from app.loading.tile_loader import NoValidTilesError
from app.worker.messages import (
  STAGE_LOAD,
  STAGE_SAVE,
  BackendFinished,
  JobFailed,
  JobFinished,
  JobProgress,
  LoadFinished,
  RunJob,
)
from app.worker.output import save_outputs

# Como mucho un mensaje de progreso cada este intervalo (salvo cambio de etapa o fin).
PROGRESS_MIN_INTERVAL_MS = 100
MS_PER_SECOND = 1000.0
STAGE_START = 0.0
STAGE_END = 1.0
OUT_OF_MEMORY_REASON = "memoria insuficiente en el dispositivo"
UNEXPECTED_REASON = "error inesperado en el worker"
# Errores esperables cuyo mensaje ya es legible para la interfaz.
READABLE_ERRORS = (InvalidParamsError, InvalidTargetError, NoValidTilesError, BackendUnavailableError)

logger = logging.getLogger(__name__)


class EventSink(Protocol):
  """Destino de los eventos (``multiprocessing.Queue`` o ``queue.Queue`` en tests)."""

  def put(self, item: object) -> None:
    """Encola un evento."""


class Loader(Protocol):
  """Carga común con reutilización (``LoadCache``)."""

  def load(self, tiles_root: str | Path, target_path: str | Path, cols: int) -> LoadResult:
    """Devuelve teselas y objetivo, decodificando solo lo que cambió."""


class BackendResolver(Protocol):
  """Selección de backends (``BackendRegistry``)."""

  def resolve(self, names: Iterable[str]) -> list[MosaicBackend]:
    """Backends pedidos, exactamente esos."""


def readable_reason(error: Exception) -> str:
  """Motivo de una falla tal como lo muestra la interfaz."""
  if isinstance(error, OutOfMemoryError | MemoryError):
    return OUT_OF_MEMORY_REASON
  if isinstance(error, READABLE_ERRORS):
    return str(error)
  return f"{UNEXPECTED_REASON}: {error}"


class ThrottledProgress:
  """Convierte el progreso de un backend en ``JobProgress`` sin saturar la cola."""

  def __init__(self, sink: EventSink, job_id: str, backend: str | None, clock: Callable[[], float] = time.monotonic):
    """``clock`` se reemplaza en los tests."""
    self._sink, self._job_id, self._backend, self._clock = sink, job_id, backend, clock
    self._last_stage: str | None = None
    self._last_time = 0.0

  def __call__(self, stage: str, fraction: float) -> None:
    """Publica si cambió la etapa, si terminó o si pasó el intervalo mínimo."""
    now = self._clock()
    elapsed_ms = (now - self._last_time) * MS_PER_SECOND
    if stage == self._last_stage and fraction < STAGE_END and elapsed_ms < PROGRESS_MIN_INTERVAL_MS:
      return
    self._last_stage, self._last_time = stage, now
    self._sink.put(JobProgress(self._job_id, self._backend, stage, fraction))


class JobRunner:
  """Ejecuta un ``RunJob`` y publica sus eventos; nunca deja escapar una excepción."""

  def __init__(self, loader: Loader, registry: BackendResolver, sink: EventSink, preview_max_side: int) -> None:
    """Recibe la cache de carga, el registro, la cola de eventos y el lado de la vista previa."""
    self._loader, self._registry, self._sink = loader, registry, sink
    self._preview_max_side = preview_max_side

  def run(self, command: RunJob) -> None:
    """Ejecuta el trabajo y publica también su evento final."""
    self._sink.put(self.execute(command))

  def execute(self, command: RunJob) -> JobFinished | JobFailed:
    """Carga, ejecuta cada backend y guarda; devuelve el evento final sin publicarlo.

    Separar el evento final le permite al worker marcarse libre antes de
    publicarlo: así un ``RunJob`` que llegue justo después de ``JobFinished``
    nunca encuentra al worker todavía ocupado.
    """
    try:
      loaded, params = self._load(command)
      choice = generate_choice(params.seed, params.k, loaded.target.rows * params.cols)
      for backend in self._registry.resolve(command.backends):
        self._run_backend(command, backend, loaded, params, choice)
    except Exception as error:
      logger.exception("falló el trabajo %s", command.job_id)
      return JobFailed(command.job_id, readable_reason(error))
    return JobFinished(command.job_id)

  def _load(self, command: RunJob) -> tuple[LoadResult, MosaicParams]:
    """Etapa común de carga; ajusta ``k`` si se descartaron archivos inválidos."""
    progress = ThrottledProgress(self._sink, command.job_id, None)
    progress(STAGE_LOAD, STAGE_START)
    loaded = self._loader.load(command.tiles_dir, command.target_path, command.params.cols)
    progress(STAGE_LOAD, STAGE_END)
    n_tiles = len(loaded.tiles.paths)
    params = dataclasses.replace(command.params, k=min(command.params.k, n_tiles))
    rows = loaded.target.rows
    load = LoadFinished(
      command.job_id,
      loaded.load_ms,
      loaded.reused,
      n_tiles,
      len(loaded.tiles.skipped),
      rows,
      params.cols,
      rows * params.cols,
    )
    self._sink.put(load)
    return loaded, params

  def _run_backend(
    self, command: RunJob, backend: MosaicBackend, loaded: LoadResult, params: MosaicParams, choice
  ) -> None:
    """Ejecuta un backend y, ya fuera de la medición, guarda la imagen."""
    progress = ThrottledProgress(self._sink, command.job_id, backend.name)
    result = backend.run(loaded.tiles.tiles_src, loaded.target.target_src, params, choice, progress)
    progress(STAGE_SAVE, STAGE_START)
    saved = save_outputs(result.image, Path(command.output_dir) / backend.name, self._preview_max_side)
    progress(STAGE_SAVE, STAGE_END)
    height, width = result.image.shape[:2]
    self._sink.put(
      BackendFinished(
        command.job_id,
        backend.name,
        result.device_name,
        result.timings,
        backend.init_ms,
        saved.png_path,
        saved.jpeg_path,
        saved.preview_path,
        width,
        height,
      )
    )
