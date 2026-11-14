"""Cliente del proceso worker (patrón Facade, design D1).

El resto del proceso web solo llama a ``start()``, ``send()`` y ``stop()`` y
recibe los eventos por un callback; ``WorkerClient`` encapsula:

- la creación del proceso con ``spawn`` y sus dos colas (órdenes y eventos);
- un **hilo lector** que consume ``event_q`` (Productor/Consumidor) y entrega
  cada evento al callback. Termina con un mensaje centinela, y como lee con
  ``get(timeout=...)`` tampoco se queda colgado si la cola quedó inutilizable;
- un **hilo monitor** que espera el ``sentinel`` del proceso: si el worker
  muere sin que se lo haya pedido, publica ``WorkerCrashed`` y lo relanza con
  colas nuevas;
- el apagado ordenado: ``Shutdown``, ``join(timeout)`` y, si no alcanzó,
  ``terminate()``.

El monitor relanza y ``stop()`` marca el apagado bajo el mismo lock de ciclo de
vida: si el worker muere justo mientras se apaga la aplicación, o el monitor
relanza antes y ``stop()`` apaga al worker nuevo, o ``stop()`` marca antes y el
monitor ya no relanza. Nunca queda un worker que nadie detiene.

El callback se llama desde los hilos del cliente: quien lo registra tiene que
pasar el evento a su propio hilo (el proceso web usa ``call_soon_threadsafe``).
"""

import dataclasses
import logging
import multiprocessing
import queue
import threading
from collections.abc import Callable
from multiprocessing.connection import wait

from app.worker.main import WorkerOptions, worker_main
from app.worker.messages import Command, Shutdown, WorkerCrashed

START_METHOD = "spawn"
# Cada cuánto el hilo lector y el monitor revisan si tienen que terminar.
POLL_INTERVAL_S = 0.5
# Espera extra después de terminate() para recolectar el proceso.
TERMINATE_JOIN_S = 5.0
# Tiempo que se le da al hilo lector para vaciar los eventos pendientes antes de soltar las colas.
READER_DRAIN_S = 2.0

EventCallback = Callable[[object], None]
WorkerTarget = Callable[..., None]

logger = logging.getLogger(__name__)


class WorkerUnavailableError(RuntimeError):
  """No hay un worker vivo al que enviarle la orden."""


class _StopReading:
  """Centinela que detiene al hilo lector (nunca lo envía el worker)."""


@dataclasses.dataclass
class _Generation:
  """Un proceso worker con sus colas; se reemplaza entero al relanzar."""

  process: multiprocessing.Process
  command_q: multiprocessing.Queue
  event_q: multiprocessing.Queue
  stop_reading: threading.Event = dataclasses.field(default_factory=threading.Event)
  reader: threading.Thread | None = None


class WorkerClient:
  """Lanza, vigila, relanza y apaga el proceso worker."""

  def __init__(
    self,
    on_event: EventCallback,
    options: WorkerOptions,
    shutdown_timeout_s: float,
    target: WorkerTarget = worker_main,
  ) -> None:
    """``target`` reemplaza a ``worker_main`` en los tests (tiene que poder importarse con spawn)."""
    self._on_event, self._options, self._timeout, self._target = on_event, options, shutdown_timeout_s, target
    self._context = multiprocessing.get_context(START_METHOD)
    self._lock = threading.Lock()
    self._lifecycle_lock = threading.Lock()
    self._stopping = threading.Event()
    self._current: _Generation | None = None
    self._monitor: threading.Thread | None = None

  @property
  def pid(self) -> int | None:
    """PID del worker actual (para diagnóstico y tests)."""
    current = self._current
    return current.process.pid if current else None

  def start(self) -> None:
    """Lanza el worker y el monitor."""
    self._stopping.clear()
    self._launch()
    self._monitor = threading.Thread(target=self._watch, name="worker-monitor", daemon=True)
    self._monitor.start()

  def send(self, command: Command) -> None:
    """Encola una orden para el worker."""
    with self._lock:
      current = self._current
      if current is None or not current.process.is_alive():
        raise WorkerUnavailableError("el worker no está en ejecución")
      current.command_q.put(command)

  def stop(self) -> None:
    """Apagado ordenado; pasado el tiempo límite termina el proceso a la fuerza."""
    with self._lifecycle_lock:
      self._stopping.set()
      current = self._current
    if current is None:
      return
    if current.process.is_alive():
      current.command_q.put(Shutdown())
    current.process.join(self._timeout)
    if current.process.is_alive():
      logger.warning("el worker no terminó en %.1f s: se lo termina", self._timeout)
      current.process.terminate()
      current.process.join(TERMINATE_JOIN_S)
    self._retire(current)
    if self._monitor is not None:
      self._monitor.join()

  def _launch(self) -> None:
    """Crea un proceso worker nuevo con colas y hilo lector nuevos."""
    command_q, event_q = self._context.Queue(), self._context.Queue()
    process = self._context.Process(target=self._target, args=(command_q, event_q, self._options), name="mosaic-worker")
    process.start()
    generation = _Generation(process, command_q, event_q)
    generation.reader = threading.Thread(target=self._read, args=(generation,), name="worker-events", daemon=True)
    with self._lock:
      self._current = generation
    generation.reader.start()

  def _read(self, generation: _Generation) -> None:
    """Hilo lector: entrega cada evento al callback hasta el centinela."""
    while not generation.stop_reading.is_set():
      try:
        event = generation.event_q.get(timeout=POLL_INTERVAL_S)
      except queue.Empty:
        continue
      except (EOFError, OSError):
        return
      if isinstance(event, _StopReading):
        return
      self._on_event(event)

  def _watch(self) -> None:
    """Monitor: si el worker muere sin que se lo pidan, avisa y lo relanza."""
    while not self._stopping.is_set():
      current = self._current
      if not wait([current.process.sentinel], POLL_INTERVAL_S):
        continue
      with self._lifecycle_lock:
        if self._stopping.is_set():
          return
        logger.error("el worker terminó inesperadamente (código %s): se relanza", current.process.exitcode)
        self._retire(current)
        self._on_event(WorkerCrashed(current.process.exitcode))
        self._launch()

  @staticmethod
  def _retire(generation: _Generation) -> None:
    """Deja que el lector vacíe los eventos pendientes (hasta el centinela) y suelta las colas."""
    generation.event_q.put(_StopReading())
    generation.reader.join(READER_DRAIN_S)
    generation.stop_reading.set()
    for channel in (generation.command_q, generation.event_q):
      channel.cancel_join_thread()
      channel.close()
