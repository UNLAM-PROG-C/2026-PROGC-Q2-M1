"""Resultado de un trabajo: imagen, top-k y tiempos por etapa."""

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

# Cómo se informa una medición que no corresponde al backend (por ejemplo,
# las transferencias host↔device en CPU). No es lo mismo que cero.
NOT_APPLICABLE = "no aplica"


class Stage(StrEnum):
  """Etapas que mide todo backend."""

  PREPARE_TILES = "prepare_tiles"
  TARGET_DESCRIPTORS = "target_descriptors"
  MATCHING = "matching"
  COMPOSE = "compose"
  TRANSFER_H2D = "transfer_h2d"
  TRANSFER_D2H = "transfer_d2h"
  STAGING_H2D = "staging_h2d"
  STAGING_D2H = "staging_d2h"


# Etapas de cómputo que se comparan entre backends, en orden de ejecución.
COMPARED_STAGES = (Stage.PREPARE_TILES, Stage.TARGET_DESCRIPTORS, Stage.MATCHING, Stage.COMPOSE)
# Etapas de transferencia, que solo existen en GPU.
TRANSFER_STAGES = (Stage.TRANSFER_H2D, Stage.TRANSFER_D2H)
# Copias en el host entre los arrays del trabajo y la memoria de staging (pinned
# en CUDA, ALLOC_HOST_PTR en OpenCL). Se informan aparte del DMA para que quede a
# la vista el costo de usar memoria page-locked (design D5 del cambio 2).
STAGING_STAGES = (Stage.STAGING_H2D, Stage.STAGING_D2H)
# Mediciones opcionales: solo existen en GPU.
OPTIONAL_STAGES = (*TRANSFER_STAGES, *STAGING_STAGES)


@dataclass(frozen=True)
class StageTimings:
  """Tiempos de un trabajo en milisegundos.

  ``None`` en una transferencia o en una copia de staging significa "no aplica".
  """

  prepare_tiles_ms: float
  target_descriptors_ms: float
  matching_ms: float
  compose_ms: float
  total_ms: float
  transfer_h2d_ms: float | None = None
  transfer_d2h_ms: float | None = None
  staging_h2d_ms: float | None = None
  staging_d2h_ms: float | None = None

  @classmethod
  def from_elapsed(cls, elapsed_ms: dict[Stage, float], total_ms: float) -> "StageTimings":
    """Arma los tiempos a partir de lo medido por un ``StageTimer``."""
    stages = {f"{stage.value}_ms": elapsed_ms[stage] for stage in COMPARED_STAGES}
    optional = {f"{stage.value}_ms": elapsed_ms.get(stage) for stage in OPTIONAL_STAGES}
    return cls(total_ms=total_ms, **stages, **optional)

  def stages_sum_ms(self) -> float:
    """Suma de todas las etapas medidas (las que no aplican cuentan cero)."""
    measured = [getattr(self, f"{stage.value}_ms") for stage in (*COMPARED_STAGES, *OPTIONAL_STAGES)]
    return sum(value for value in measured if value is not None)

  def to_dict(self) -> dict[str, float | str]:
    """Serializa los tiempos; las transferencias ausentes quedan como "no aplica"."""
    values = {name: getattr(self, name) for name in self.__dataclass_fields__}
    return {name: NOT_APPLICABLE if value is None else value for name, value in values.items()}


@dataclass(frozen=True)
class MosaicResult:
  """Salida de un backend para un trabajo.

  Attributes:
    image: imagen final ``[rows·tile_px, cols·tile_px, 3]`` uint8.
    topk_idx: candidatos por celda ``[M, k]`` int32, de mejor a peor.
    topk_dist: distancias de esos candidatos ``[M, k]`` float32.
    timings: tiempos por etapa y total.
    backend_name: nombre del backend que lo produjo.
    device_name: dispositivo en el que corrió.
    notes: avisos del trabajo (por ejemplo, "transferencia sin memoria pinned").
  """

  image: np.ndarray
  topk_idx: np.ndarray
  topk_dist: np.ndarray
  timings: StageTimings
  backend_name: str
  device_name: str
  notes: tuple[str, ...] = ()
