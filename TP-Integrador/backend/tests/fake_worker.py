"""Workers falsos para los tests de ``WorkerClient``.

Tienen que estar en un módulo importable (no dentro de un test) porque el
proceso se crea con ``spawn`` y el hijo importa la función por nombre.
"""

import os
import time

from app.backends.registry import BackendStatus, GpuPreference
from app.worker.messages import JobFinished, Shutdown, WorkerReady

CRASH_JOB_ID = "crash"
CRASH_EXIT_CODE = 3
STUBBORN_SLEEP_S = 60.0


def _ready() -> WorkerReady:
  return WorkerReady((BackendStatus("cpu", True, "falsa"),), GpuPreference(None, "sin GPU"), None)


def fake_worker_main(command_q, event_q, options) -> None:
  """Responde cada trabajo con ``JobFinished``; el trabajo "crash" mata el proceso."""
  event_q.put(_ready())
  while True:
    command = command_q.get()
    if isinstance(command, Shutdown):
      return
    if command.job_id == CRASH_JOB_ID:
      os._exit(CRASH_EXIT_CODE)
    event_q.put(JobFinished(command.job_id))


def stubborn_worker_main(command_q, event_q, options) -> None:
  """Ignora ``Shutdown``: obliga al cliente a usar ``terminate()``."""
  event_q.put(_ready())
  time.sleep(STUBBORN_SLEEP_S)
