"""Punto de entrada del proceso worker (design D1).

El worker es el único dueño de los contextos CUDA/OpenCL y del pool de
decodificación. Tiene dos hilos:

- el **hilo de trabajo** (el principal) crea los backends, ejecuta los trabajos
  de a uno y los libera al final. Los contextos de GPU se crean y se usan solo
  desde este hilo;
- el **hilo de órdenes** lee ``command_q``. Si llega un ``RunJob`` mientras hay
  otro en curso lo rechaza (``JobRejected``) sin interrumpir al hilo de trabajo;
  si no, se lo pasa por una cola interna (Productor/Consumidor).

Ctrl+C llega a todos los procesos de la consola (en Windows también), así que
el worker y su pool ignoran ``SIGINT``: solo terminan con ``Shutdown`` o con el
``terminate()`` del proceso web pasado el tiempo límite.
"""

import logging
import queue
import signal
import threading
from dataclasses import dataclass

from app.backends.cpu.calibration import CpuCalibration, calibrate_cpu
from app.backends.registry import CPU, DEFAULT_FACTORIES, BackendRegistry
from app.config import DEFAULT_PREVIEW_MAX_SIDE
from app.loading.cache import LoadCache
from app.loading.tile_loader import TileLoader
from app.worker.job_runner import EventSink, JobRunner
from app.worker.messages import JobRejected, RunJob, Shutdown, WorkerReady

BUSY_REASON = "ya hay un trabajo en curso"
# Señales de consola que llegan a todo el grupo de procesos. SIGBREAK solo existe
# en Windows (Ctrl+Break); uvicorn también la usa para apagarse.
CONSOLE_SIGNALS = ("SIGINT", "SIGBREAK")
LOG_FORMAT = "%(levelname)s worker %(name)s: %(message)s"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerOptions:
  """Configuración del worker; viaja por pickle al crear el proceso.

  Attributes:
    decode_processes: procesos del pool de decodificación (0 = uno por núcleo).
    preview_max_side: lado mayor de la vista previa.
    backends: backends a detectar (``None`` = todos; los tests usan solo CPU).
  """

  decode_processes: int = 0
  preview_max_side: int = DEFAULT_PREVIEW_MAX_SIDE
  backends: tuple[str, ...] | None = None


def ignore_sigint() -> None:
  """Ignora Ctrl+C (y Ctrl+Break en Windows) en este proceso: worker y procesos del pool."""
  for name in CONSOLE_SIGNALS:
    if hasattr(signal, name):
      signal.signal(getattr(signal, name), signal.SIG_IGN)


def _create_registry(options: WorkerOptions) -> BackendRegistry:
  """Registro con todas las fábricas o solo con las pedidas."""
  if options.backends is None:
    return BackendRegistry()
  return BackendRegistry({name: DEFAULT_FACTORIES[name] for name in options.backends})


def _calibrate(registry: BackendRegistry) -> CpuCalibration | None:
  """Calibración de CPU, o ``None`` si CPU no está o la medición falla."""
  if not registry.status(CPU).available:
    return None
  try:
    return calibrate_cpu(registry.resolve([CPU])[0])
  except Exception:
    logger.exception("falló la calibración de CPU")
    return None


class CommandReader:
  """Hilo de órdenes: acepta un trabajo por vez y rechaza los demás."""

  def __init__(self, command_q, event_q: EventSink) -> None:
    """Recibe las colas del proceso web."""
    self._command_q, self._event_q = command_q, event_q
    self.accepted: queue.Queue = queue.Queue()
    self._busy = threading.Event()

  def start(self) -> threading.Thread:
    """Arranca el hilo lector."""
    thread = threading.Thread(target=self._read, name="worker-commands", daemon=True)
    thread.start()
    return thread

  def job_done(self) -> None:
    """El hilo de trabajo terminó el trabajo en curso."""
    self._busy.clear()

  def _read(self) -> None:
    """Bucle de órdenes hasta recibir ``Shutdown``."""
    while True:
      command = self._command_q.get()
      if isinstance(command, Shutdown):
        self.accepted.put(command)
        return
      if isinstance(command, RunJob) and self._busy.is_set():
        self._event_q.put(JobRejected(command.job_id, BUSY_REASON))
        continue
      self._busy.set()
      self.accepted.put(command)


def _serve(reader: CommandReader, runner: JobRunner, event_q: EventSink) -> None:
  """Hilo de trabajo: ejecuta los trabajos aceptados hasta ``Shutdown``.

  El worker se marca libre antes de publicar el evento final: el proceso web
  acepta un trabajo nuevo recién al recibir ese evento, así que el hilo de
  órdenes nunca lo rechaza por un ``busy`` que quedó atrasado.
  """
  while True:
    command = reader.accepted.get()
    if isinstance(command, Shutdown):
      return
    try:
      final_event = runner.execute(command)
    finally:
      reader.job_done()
    event_q.put(final_event)


def worker_main(command_q, event_q, options: WorkerOptions) -> None:
  """Detecta y precalienta backends, calibra, crea el pool y atiende órdenes."""
  ignore_sigint()
  logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
  registry = _create_registry(options)
  tile_loader = TileLoader(options.decode_processes or None, initializer=ignore_sigint)
  try:
    statuses = registry.detect_and_warmup()
    calibration = _calibrate(registry)
    tile_loader.start()
    event_q.put(WorkerReady(tuple(statuses), registry.preferred_gpu(), calibration))
    reader = CommandReader(command_q, event_q)
    reader.start()
    _serve(reader, JobRunner(LoadCache(tile_loader), registry, event_q, options.preview_max_side), event_q)
  finally:
    tile_loader.close()
    registry.close()
    logger.info("worker detenido: pool cerrado y contextos liberados")
