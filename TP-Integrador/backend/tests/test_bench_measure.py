import numpy as np

from app.bench.measure import Benchmark, BenchmarkConfig
from app.core.backend import OutOfMemoryError
from app.core.constants import CELL_PX, RGB_CHANNELS
from app.core.result import MosaicResult, StageTimings

TILE_PX = 16
REPEATS = 3


class FakeBackend:
  """Backend falso: anota cada ejecución y devuelve un resultado determinista."""

  def __init__(self, name: str, differs: bool = False, fails: bool = False) -> None:
    self.name, self.device_name, self.init_ms = name, f"fake {name}", 0.0
    self.differs, self.fails = differs, fails
    self.calls: list[tuple[int, int]] = []

  def warmup(self) -> float:
    return 0.0

  def run(self, tiles_src, target_src, params, choice, on_progress=None) -> MosaicResult:
    rows = target_src.shape[0] // CELL_PX
    m_cells = rows * params.cols
    self.calls.append((tiles_src.shape[0], m_cells))
    if self.fails:
      raise OutOfMemoryError("sin memoria")
    topk_idx = (np.arange(m_cells * params.k, dtype=np.int32) % tiles_src.shape[0]).reshape(m_cells, params.k)
    if self.differs:
      topk_idx[0, 0] += 1
    image = np.zeros((rows * params.tile_px, params.cols * params.tile_px, RGB_CHANNELS), dtype=np.uint8)
    timings = StageTimings(1.0, 1.0, 1.0, 1.0, total_ms=float(len(self.calls)))
    return MosaicResult(image, topk_idx, np.zeros(topk_idx.shape, np.float32), timings, self.name, self.device_name)


def config(max_cpu_seconds: float = 1e9) -> BenchmarkConfig:
  return BenchmarkConfig((20, 10), (12, 6), TILE_PX, 5, 1.0, 0, REPEATS, max_cpu_seconds)


def run(backends, max_cpu_seconds: float = 1e9, estimator=None):
  return Benchmark(backends, config(max_cpu_seconds), estimator, log=lambda line: None).run()


def test_combinations_run_in_increasing_m_times_n_with_all_repeats():
  cpu = FakeBackend("cpu")
  combos = run([cpu])
  expected_order = [(10, 6), (10, 12), (20, 6), (20, 12)]
  assert [(combo.n_tiles, combo.m_cells) for combo in combos] == expected_order
  assert cpu.calls == [pair for pair in expected_order for _ in range(REPEATS)]
  assert all(len(combo.outcomes["cpu"].timings) == REPEATS for combo in combos)


def test_cpu_is_skipped_when_estimate_exceeds_maximum():
  cpu, cuda = FakeBackend("cpu"), FakeBackend("cuda")
  combos = run([cuda, cpu], max_cpu_seconds=150, estimator=lambda n_tiles, m_cells: float(n_tiles * m_cells))
  largest = combos[-1].outcomes["cpu"]
  assert largest.skipped and largest.estimated_seconds == 240.0 and not largest.timings
  assert (20, 12) not in cpu.calls and len(cpu.calls) == 3 * REPEATS
  assert len(cuda.calls) == 4 * REPEATS
  assert combos[0].outcomes["cpu"].measured


def test_reference_is_cpu_when_it_ran():
  combos = run([FakeBackend("cuda"), FakeBackend("opencl", differs=True), FakeBackend("cpu")])
  for combo in combos:
    assert combo.verification.reference == "cpu"
    assert combo.verification.differences["opencl"].topk_cells == 1
    assert combo.verification.differences["cuda"].total_cells == 0


def test_reference_is_first_backend_when_cpu_is_skipped():
  backends = [FakeBackend("cuda"), FakeBackend("opencl"), FakeBackend("cpu")]
  combos = run(backends, max_cpu_seconds=0, estimator=lambda n_tiles, m_cells: 1.0)
  assert all(combo.verification.reference == "cuda" for combo in combos)
  assert all(set(combo.verification.differences) == {"opencl"} for combo in combos)


def test_single_backend_has_no_verification():
  assert all(combo.verification is None for combo in run([FakeBackend("cuda")]))


def test_failed_backend_is_reported_and_others_continue():
  failing, cpu = FakeBackend("cuda", fails=True), FakeBackend("cpu")
  combos = run([failing, cpu])
  for combo in combos:
    assert combo.outcomes["cuda"].failure and not combo.outcomes["cuda"].measured
    assert combo.outcomes["cpu"].measured
    assert combo.verification is None


def test_k_is_clamped_to_n():
  small = BenchmarkConfig((3,), (6,), TILE_PX, 5, 1.0, 0, 1, 1e9)
  combo = Benchmark([FakeBackend("cpu")], small, log=lambda line: None).run()[0]
  assert combo.outcomes["cpu"].measured
