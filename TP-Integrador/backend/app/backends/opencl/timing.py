"""Medición por profiling de OpenCL (estrategia ``StageTimer`` del backend OpenCL).

La cola se crea con ``PROFILING_ENABLE``: cada comando encolado devuelve un
evento con los contadores ``profile.start`` y ``profile.end`` (en ns). Entre
``start(stage)`` y ``stop(stage)`` el backend agrega los eventos de los comandos
de la etapa; su tiempo es desde el inicio del primero hasta el fin del último.
Los contadores se leen recién en ``elapsed_ms()``, con el trabajo terminado. Las
copias a/desde staging ocurren en el host y se miden con reloj de pared.
"""

from typing import Any

from app.core.result import Stage

NS_PER_MS = 1e6


def span_ms(events: list[Any]) -> float:
  """Milisegundos desde el inicio del primer evento hasta el fin del último."""
  if not events:
    return 0.0
  start = min(event.profile.start for event in events)
  end = max(event.profile.end for event in events)
  return (end - start) / NS_PER_MS


class OpenClProfilingTimer:
  """Junta los eventos de cada etapa y calcula su duración por profiling."""

  def __init__(self) -> None:
    """Crea un timer sin mediciones."""
    self._events: dict[Stage, list[Any]] = {}
    self._current: Stage | None = None
    self._host_ms: dict[Stage, float] = {}

  def start(self, stage: Stage) -> None:
    """Desde acá, los eventos agregados pertenecen a ``stage``."""
    self._events[stage] = []
    self._current = stage

  def stop(self, stage: Stage) -> None:
    """Cierra la etapa (sin esperar: los eventos se leen al final)."""
    self._current = None

  def add(self, event: Any) -> None:
    """Agrega el evento de un comando a la etapa abierta, si hay una."""
    if self._current is not None:
      self._events[self._current].append(event)

  def record_host(self, stage: Stage, elapsed_ms: float) -> None:
    """Suma un tiempo medido en el host (copias a/desde staging)."""
    self._host_ms[stage] = self._host_ms.get(stage, 0.0) + elapsed_ms

  def elapsed_ms(self) -> dict[Stage, float]:
    """Duración de cada etapa según el profiling, más los tiempos de host."""
    elapsed = dict(self._host_ms)
    elapsed.update({stage: span_ms(events) for stage, events in self._events.items()})
    return elapsed
