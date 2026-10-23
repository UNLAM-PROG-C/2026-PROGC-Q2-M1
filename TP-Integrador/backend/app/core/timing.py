"""Medición de etapas (patrón Strategy).

Cada backend elige cómo se mide una etapa: en CPU alcanza con
``time.perf_counter``; en GPU (cambio 2) se usan eventos de CUDA o el
profiling de OpenCL. ``BaseBackend.run()`` solo conoce la interfaz
``StageTimer``.
"""

import time
from typing import Protocol

from app.core.result import Stage

# Milisegundos por segundo.
MS_PER_SECOND = 1000.0


def elapsed_ms_since(start_seconds: float) -> float:
  """Milisegundos transcurridos desde ``start_seconds`` (de ``perf_counter``)."""
  return (time.perf_counter() - start_seconds) * MS_PER_SECOND


class StageTimer(Protocol):
  """Estrategia de medición de etapas."""

  def start(self, stage: Stage) -> None:
    """Marca el inicio de una etapa."""

  def stop(self, stage: Stage) -> None:
    """Marca el fin de una etapa (una vez terminada efectivamente)."""

  def elapsed_ms(self) -> dict[Stage, float]:
    """Devuelve la duración de cada etapa medida; se llama al final del trabajo."""


class PerfCounterTimer:
  """Mide con el reloj monotónico de alta resolución del host."""

  def __init__(self) -> None:
    """Crea un timer sin mediciones."""
    self._starts: dict[Stage, float] = {}
    self._elapsed: dict[Stage, float] = {}

  def start(self, stage: Stage) -> None:
    """Marca el inicio de una etapa."""
    self._starts[stage] = time.perf_counter()

  def stop(self, stage: Stage) -> None:
    """Marca el fin de una etapa; en CPU la etapa ya terminó al volver la llamada."""
    self._elapsed[stage] = elapsed_ms_since(self._starts.pop(stage))

  def elapsed_ms(self) -> dict[Stage, float]:
    """Devuelve la duración de cada etapa medida."""
    return dict(self._elapsed)
