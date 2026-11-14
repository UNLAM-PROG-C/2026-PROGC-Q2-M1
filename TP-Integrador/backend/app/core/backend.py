"""Contrato común de los backends de fotomosaico.

Patrones:
- Strategy: ``MosaicBackend`` es la interfaz que cumplen CPU, CUDA y OpenCL;
  el algoritmo es el mismo y cambia cómo se ejecuta y cómo se mide.
- Template Method: ``BaseBackend.run()`` fija la secuencia de etapas, el
  cronometraje y el progreso; cada backend implementa solo los pasos. Así las
  tres implementaciones miden exactamente las mismas etapas.
- Observer: el callback ``on_progress`` desacopla al backend de quién recibe
  el progreso (un test, el worker, el benchmark).
"""

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Protocol

import numpy as np

from app.core.job import MosaicJob
from app.core.params import MosaicParams
from app.core.result import MosaicResult, Stage, StageTimings
from app.core.timing import StageTimer, elapsed_ms_since

# Callback de progreso: (nombre de la etapa, fracción en [0, 1]).
ProgressCallback = Callable[[str, float], None]
# Callback que recibe un paso para informar el avance dentro de su etapa.
StepProgress = Callable[[float], None]
# Paso de cómputo de una etapa.
Step = Callable[[MosaicJob, StepProgress], None]

PROGRESS_START = 0.0
PROGRESS_END = 1.0


class BackendError(RuntimeError):
  """Error de ejecución de un backend; el backend sigue usable después."""


class OutOfMemoryError(BackendError):
  """El trabajo no entra en la memoria disponible."""


class BackendInitError(BackendError):
  """El backend no se pudo inicializar; ``reason`` es el motivo corto que se informa."""

  def __init__(self, reason: str, detail: str = "") -> None:
    """Guarda el motivo corto; el detalle (por ejemplo, un build log) va al mensaje."""
    super().__init__(f"{reason}: {detail}" if detail else reason)
    self.reason = reason


class MosaicBackend(Protocol):
  """Interfaz que cumple todo backend."""

  name: str
  device_name: str
  init_ms: float | None

  def warmup(self) -> float:
    """Paga los costos únicos (compilación) y devuelve su duración en ms."""

  def run(
    self,
    tiles_src: np.ndarray,
    target_src: np.ndarray,
    params: MosaicParams,
    choice: np.ndarray,
    on_progress: ProgressCallback | None = None,
  ) -> MosaicResult:
    """Ejecuta un trabajo y devuelve la imagen, el top-k y los tiempos."""


class ProgressReporter:
  """Reenvía el progreso al observador, si hay uno."""

  def __init__(self, on_progress: ProgressCallback | None) -> None:
    """Guarda el callback (puede ser ``None``)."""
    self._on_progress = on_progress

  def report(self, stage: Stage, fraction: float) -> None:
    """Informa la fracción completada de una etapa."""
    if self._on_progress is not None:
      self._on_progress(stage.value, fraction)

  def for_stage(self, stage: Stage) -> StepProgress:
    """Devuelve un callback que informa el avance dentro de ``stage``."""
    return lambda fraction: self.report(stage, fraction)


class BaseBackend(ABC):
  """Esqueleto común: secuencia de etapas, cronometraje y progreso."""

  name = "base"

  def __init__(self, device_name: str) -> None:
    """Crea el backend sin inicializar."""
    self.device_name = device_name
    self.init_ms: float | None = None

  def warmup(self) -> float:
    """Ejecuta la inicialización una sola vez y mide su duración."""
    start = time.perf_counter()
    self._warmup()
    self.init_ms = elapsed_ms_since(start)
    return self.init_ms

  def run(
    self,
    tiles_src: np.ndarray,
    target_src: np.ndarray,
    params: MosaicParams,
    choice: np.ndarray,
    on_progress: ProgressCallback | None = None,
  ) -> MosaicResult:
    """Valida, ejecuta las etapas en orden y arma el resultado."""
    if self.init_ms is None:
      self.warmup()
    job = MosaicJob.create(tiles_src, target_src, params, choice)
    try:
      return self._execute(job, self._create_progress(on_progress))
    except MemoryError as error:
      raise OutOfMemoryError(f"memoria insuficiente para el trabajo en {self.name}") from error
    finally:
      self._release(job)

  def _execute(self, job: MosaicJob, progress: ProgressReporter) -> MosaicResult:
    """Secuencia fija de etapas (Template Method)."""
    timer = self._create_timer()
    start = time.perf_counter()
    self._upload(job, timer)
    for stage, step in self._compute_steps():
      self._run_stage(job, stage, step, timer, progress)
    image = self._download(job, timer)
    total_ms = elapsed_ms_since(start)
    timings = StageTimings.from_elapsed(timer.elapsed_ms(), total_ms)
    topk_idx, topk_dist = self._collect_topk(job)
    return MosaicResult(image, topk_idx, topk_dist, timings, self.name, self.device_name, tuple(job.notes))

  def _compute_steps(self) -> tuple[tuple[Stage, Step], ...]:
    """Etapas de cómputo comparadas, en orden."""
    return (
      (Stage.PREPARE_TILES, self._prepare_tiles),
      (Stage.TARGET_DESCRIPTORS, self._target_descriptors),
      (Stage.MATCHING, self._match),
      (Stage.COMPOSE, self._compose),
    )

  @staticmethod
  def _run_stage(job: MosaicJob, stage: Stage, step: Step, timer: StageTimer, progress: ProgressReporter) -> None:
    """Ejecuta un paso midiéndolo e informando su inicio y su fin."""
    progress.report(stage, PROGRESS_START)
    timer.start(stage)
    step(job, progress.for_stage(stage))
    timer.stop(stage)
    progress.report(stage, PROGRESS_END)

  # --- Pasos que implementa cada backend ---------------------------------------

  @abstractmethod
  def _warmup(self) -> None:
    """Compila y ejecuta un trabajo mínimo para pagar los costos únicos."""

  @abstractmethod
  def _create_timer(self) -> StageTimer:
    """Devuelve la estrategia de medición de este backend."""

  def _create_progress(self, on_progress: ProgressCallback | None) -> ProgressReporter:
    """Devuelve quién reenvía el progreso; en GPU se difiere hasta que el dispositivo avanza."""
    return ProgressReporter(on_progress)

  def _upload(self, job: MosaicJob, timer: StageTimer) -> None:  # noqa: B027 (gancho opcional)
    """Copia las entradas al dispositivo; por defecto no hay transferencias."""

  @abstractmethod
  def _prepare_tiles(self, job: MosaicJob, report: StepProgress) -> None:
    """Redimensiona las teselas y calcula sus descriptores y normas."""

  @abstractmethod
  def _target_descriptors(self, job: MosaicJob, report: StepProgress) -> None:
    """Calcula los descriptores y normas de las celdas del objetivo."""

  @abstractmethod
  def _match(self, job: MosaicJob, report: StepProgress) -> None:
    """Calcula distancias y top-k por bloques de celdas."""

  @abstractmethod
  def _compose(self, job: MosaicJob, report: StepProgress) -> None:
    """Compone la imagen final."""

  @abstractmethod
  def _download(self, job: MosaicJob, timer: StageTimer) -> np.ndarray:
    """Devuelve la imagen final en memoria del host (dentro de la medición)."""

  @abstractmethod
  def _collect_topk(self, job: MosaicJob) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve ``topk_idx`` y ``topk_dist`` en el host (fuera de la medición)."""

  def _release(self, job: MosaicJob) -> None:
    """Libera los buffers del trabajo, también si falló."""
    job.buffers.clear()
