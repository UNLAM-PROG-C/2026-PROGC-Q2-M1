"""Medición con eventos CUDA (estrategia ``StageTimer`` del backend CUDA).

Cada etapa y cada grupo de transferencias se mide con un par de eventos
registrados en el stream del trabajo: el de inicio antes del primer comando y
el de fin después del último. Registrar un evento no espera nada; la lectura de
los tiempos se difiere hasta ``elapsed_ms()``, que se llama cuando el trabajo
ya terminó. Las copias a/desde staging ocurren en el host y se miden con reloj
de pared (``record_host``).
"""

from collections.abc import Callable
from typing import Any

from app.core.result import Stage


class CudaEventTimer:
  """Pares de eventos CUDA por etapa, leídos al final del trabajo."""

  def __init__(self, stream: Any, event_factory: Callable[[], Any]) -> None:
    """``event_factory`` es ``pycuda.driver.Event`` (se inyecta para no importar PyCUDA acá)."""
    self._stream = stream
    self._event_factory = event_factory
    self._events: dict[Stage, list[Any]] = {}
    self._host_ms: dict[Stage, float] = {}

  def _record(self) -> Any:
    """Registra un evento en el stream del trabajo."""
    event = self._event_factory()
    event.record(self._stream)
    return event

  def start(self, stage: Stage) -> None:
    """Registra el evento de inicio de la etapa."""
    self._events[stage] = [self._record()]

  def stop(self, stage: Stage) -> None:
    """Registra el evento de fin de la etapa (sin esperar)."""
    self._events[stage].append(self._record())

  def record_host(self, stage: Stage, elapsed_ms: float) -> None:
    """Suma un tiempo medido en el host (copias a/desde staging)."""
    self._host_ms[stage] = self._host_ms.get(stage, 0.0) + elapsed_ms

  def elapsed_ms(self) -> dict[Stage, float]:
    """Milisegundos entre cada par de eventos (espera al de fin) más los tiempos de host."""
    elapsed = dict(self._host_ms)
    for stage, (start, end) in self._events.items():
      end.synchronize()
      elapsed[stage] = start.time_till(end)
    return elapsed
