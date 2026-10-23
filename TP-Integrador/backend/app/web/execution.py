"""Formas de ejecución de la interfaz → backends concretos (design D4).

La interfaz no habla de backends sino de formas de ejecución: ``cpu`` o
``gpu``. La GPU es la que eligió el registro en el worker (``preferred_gpu()``:
CUDA si está disponible, si no OpenCL). Pedir ``gpu`` sin GPU se rechaza con el
motivo; nunca se cae a CPU en silencio. El cambio 4 agrega ``both`` sumando una
entrada a ``MODES`` que devuelva ``(cpu, gpu)``: el protocolo ya lleva una
lista de backends.
"""

from app.backends.registry import CPU, DISPLAY_NAMES
from app.core.constants import DEFAULT_K
from app.worker.messages import WorkerReady

CPU_MODE = "cpu"
GPU_MODE = "gpu"
MODES = (CPU_MODE, GPU_MODE)
WORKER_NOT_READY_REASON = "el worker todavía está detectando los backends"


class ExecutionModeError(ValueError):
  """La forma de ejecución pedida no está disponible; el mensaje es el motivo."""


def _cpu_status(ready: WorkerReady):
  """Estado del backend CPU informado por el worker, si existe."""
  return next((status for status in ready.statuses if status.name == CPU), None)


def backends_for_mode(mode: str, ready: WorkerReady | None) -> tuple[str, ...]:
  """Lista explícita de backends para una forma de ejecución."""
  if ready is None:
    raise ExecutionModeError(WORKER_NOT_READY_REASON)
  if mode == CPU_MODE:
    status = _cpu_status(ready)
    if status is None or not status.available:
      raise ExecutionModeError(f"CPU no disponible: {status.reason if status else 'no detectada'}")
    return (CPU,)
  if mode == GPU_MODE:
    if ready.preferred_gpu.status is None:
      raise ExecutionModeError(ready.preferred_gpu.reason)
    return (ready.preferred_gpu.status.name,)
  raise ExecutionModeError(f"forma de ejecución desconocida: {mode} (opciones: {', '.join(MODES)})")


def effective_k(n_tiles: int) -> int:
  """``k`` no lo elige la persona: el valor por defecto, acotado por N."""
  return min(DEFAULT_K, n_tiles)


def execution_options(ready: WorkerReady | None) -> dict:
  """Opciones del paso 3 ya resueltas, para ``/api/state``."""
  if ready is None:
    return {
      "cpu": {"available": False, "device": None},
      "gpu": {"available": False, "api": None, "device": None, "reason": WORKER_NOT_READY_REASON},
    }
  cpu = _cpu_status(ready)
  gpu = ready.preferred_gpu.status
  return {
    "cpu": {"available": bool(cpu and cpu.available), "device": cpu.device_name if cpu else None},
    "gpu": {
      "available": gpu is not None,
      "api": DISPLAY_NAMES[gpu.name] if gpu else None,
      "device": gpu.device_name if gpu else None,
      "reason": None if gpu else ready.preferred_gpu.reason,
    },
  }
