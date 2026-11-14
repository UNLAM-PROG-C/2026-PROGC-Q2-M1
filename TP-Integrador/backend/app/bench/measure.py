"""Bucle de medición del benchmark (design D3 del cambio 5).

Las combinaciones (N, M) se recorren en orden creciente de M·N. Para cada una
se generan los datos sintéticos una sola vez y se ejecutan los backends de a
uno, cada uno ``repeats`` veces con el mismo ``choice``: nada corre en paralelo
con la medición. Los backends ya llegan precalentados (``warmup()`` lo hace el
registro al detectarlos), así que ninguna repetición paga la compilación.

Antes de CPU se consulta la estimación calibrada y, si supera el máximo, la
combinación se registra como omitida. De la primera repetición de cada backend
se toma la huella de ``app/core/verification.py`` y la imagen se libera al
volver de la ejecución: nunca hay dos imágenes finales en memoria. Al terminar
la combinación, los arrays de entrada salen de alcance y se liberan antes de
generar los de la siguiente.
"""

import functools
import itertools
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from app.backends.registry import CPU
from app.bench.synthetic import grid_shape, synthetic_target, synthetic_tiles
from app.core.backend import BackendError, MosaicBackend
from app.core.choice import generate_choice
from app.core.params import MosaicParams
from app.core.result import StageTimings
from app.core.verification import ResultFingerprint, VerificationSummary, fingerprint, verify

# Estimación de CPU en segundos para (N, M).
CpuEstimator = Callable[[int, int], float]
# Destino de las líneas de progreso (por defecto, la consola).
EventLog = Callable[[str], None]
# Cada línea se ve apenas se escribe, también si la salida va a un archivo o a `tee`.
print_now = functools.partial(print, flush=True)
FIRST_REPETITION = 1
# Hacen falta al menos dos huellas para comparar algo.
MIN_FINGERPRINTS_TO_VERIFY = 2


@dataclass(frozen=True)
class BenchmarkConfig:
  """Grilla de tamaños, parámetros del trabajo y repeticiones."""

  n_values: tuple[int, ...]
  m_values: tuple[int, ...]
  tile_px: int
  k: int
  alpha: float
  seed: int
  repeats: int
  max_cpu_seconds: float

  def combinations(self) -> list[tuple[int, int]]:
    """Pares (N, M) en orden creciente de M·N (a igual producto, primero el de menor N)."""
    pairs = itertools.product(self.n_values, self.m_values)
    return sorted(pairs, key=lambda pair: (pair[0] * pair[1], pair[0]))


@dataclass
class BackendOutcome:
  """Lo que pasó con un backend en una combinación: repeticiones, omisión o falla."""

  name: str
  device_name: str
  timings: list[StageTimings] = field(default_factory=list)
  estimated_seconds: float | None = None
  skipped: bool = False
  failure: str | None = None

  @property
  def measured(self) -> bool:
    """Se ejecutó y terminaron todas las repeticiones."""
    return bool(self.timings) and not self.skipped and self.failure is None

  def median_total_ms(self) -> float:
    """Mediana del total entre repeticiones."""
    return statistics.median(timing.total_ms for timing in self.timings)

  def min_total_ms(self) -> float:
    """Mínimo del total entre repeticiones."""
    return min(timing.total_ms for timing in self.timings)


@dataclass
class ComboResult:
  """Resultados de una combinación (N, M) para todos los backends."""

  n_tiles: int
  m_cells: int
  rows: int
  cols: int
  outcomes: dict[str, BackendOutcome] = field(default_factory=dict)
  verification: VerificationSummary | None = None

  @property
  def pairs(self) -> int:
    """Tamaño del problema M·N (pares celda-tesela)."""
    return self.n_tiles * self.m_cells


@dataclass(frozen=True)
class _Inputs:
  """Entradas de una combinación, compartidas por todos los backends."""

  tiles_src: np.ndarray
  target_src: np.ndarray
  params: MosaicParams
  choice: np.ndarray


def _make_inputs(config: BenchmarkConfig, n_tiles: int, rows: int, cols: int) -> _Inputs:
  """Datos sintéticos y ``choice`` de una combinación (``k`` no puede superar N)."""
  params = MosaicParams(
    cols=cols, tile_px=config.tile_px, k=min(config.k, n_tiles), alpha=config.alpha, seed=config.seed
  )
  choice = generate_choice(params.seed, params.k, rows * cols)
  tiles = synthetic_tiles(n_tiles, config.seed)
  return _Inputs(tiles, synthetic_target(rows, cols, config.seed), params, choice)


def _run_once(backend: MosaicBackend, inputs: _Inputs, keep_fingerprint: bool):
  """Una ejecución; la imagen se libera al volver (solo sobrevive su huella)."""
  result = backend.run(inputs.tiles_src, inputs.target_src, inputs.params, inputs.choice)
  print_ = fingerprint(result.image, result.topk_idx, inputs.params.tile_px) if keep_fingerprint else None
  return result.timings, print_


class Benchmark:
  """Mide los backends sobre la grilla de tamaños, de a una ejecución por vez."""

  def __init__(
    self,
    backends: list[MosaicBackend],
    config: BenchmarkConfig,
    cpu_estimator: CpuEstimator | None = None,
    log: EventLog = print_now,
  ) -> None:
    """``cpu_estimator`` es ``None`` si CPU no se mide o no está calibrada."""
    self._backends, self._config = backends, config
    self._cpu_estimator, self._log = cpu_estimator, log

  def run(self) -> list[ComboResult]:
    """Ejecuta todas las combinaciones en orden creciente de M·N."""
    return [self._run_combo(n_tiles, m_cells) for n_tiles, m_cells in self._config.combinations()]

  def _run_combo(self, n_tiles: int, m_cells: int) -> ComboResult:
    """Genera los datos, mide cada backend y verifica contra la referencia."""
    rows, cols = grid_shape(m_cells)
    self._log(f"N = {n_tiles}, M = {m_cells} ({rows} × {cols} celdas)")
    inputs = _make_inputs(self._config, n_tiles, rows, cols)
    combo = ComboResult(n_tiles, m_cells, rows, cols)
    fingerprints: dict[str, ResultFingerprint] = {}
    for backend in self._backends:
      combo.outcomes[backend.name] = self._run_backend(backend, inputs, combo, fingerprints)
    combo.verification = _verify(fingerprints)
    return combo

  def _run_backend(
    self, backend: MosaicBackend, inputs: _Inputs, combo: ComboResult, fingerprints: dict[str, ResultFingerprint]
  ) -> BackendOutcome:
    """Repeticiones de un backend; CPU se omite si la estimación supera el máximo."""
    outcome = BackendOutcome(backend.name, backend.device_name, estimated_seconds=self._estimate(backend, combo))
    if outcome.estimated_seconds is not None and outcome.estimated_seconds > self._config.max_cpu_seconds:
      outcome.skipped = True
      self._log(f"  {backend.name}: omitido (estimado {outcome.estimated_seconds:.0f} s)")
      return outcome
    try:
      self._repeat(backend, inputs, outcome, fingerprints)
    except BackendError as error:
      outcome.failure = str(error)
      fingerprints.pop(backend.name, None)
      self._log(f"  {backend.name}: falló ({error})")
    return outcome

  def _repeat(
    self, backend: MosaicBackend, inputs: _Inputs, outcome: BackendOutcome, fingerprints: dict[str, ResultFingerprint]
  ) -> None:
    """``repeats`` ejecuciones con el mismo ``choice``; de la primera se guarda la huella."""
    for repetition in range(FIRST_REPETITION, self._config.repeats + 1):
      timings, print_ = _run_once(backend, inputs, keep_fingerprint=repetition == FIRST_REPETITION)
      outcome.timings.append(timings)
      if print_ is not None:
        fingerprints[backend.name] = print_
      self._log(f"  {backend.name} {repetition}/{self._config.repeats}: {timings.total_ms:.1f} ms")

  def _estimate(self, backend: MosaicBackend, combo: ComboResult) -> float | None:
    """Segundos estimados en CPU (solo para el backend CPU con calibración)."""
    if backend.name != CPU or self._cpu_estimator is None:
      return None
    return self._cpu_estimator(combo.n_tiles, combo.m_cells)


def _verify(fingerprints: dict[str, ResultFingerprint]) -> VerificationSummary | None:
  """Compara contra CPU si se ejecutó; si no, contra el primer backend medido."""
  if len(fingerprints) < MIN_FINGERPRINTS_TO_VERIFY:
    return None
  reference = CPU if CPU in fingerprints else next(iter(fingerprints))
  return verify(fingerprints, reference)
