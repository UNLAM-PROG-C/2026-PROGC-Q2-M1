"""Contrato de backend: Template Method, progreso, tiempos y errores aislados."""

import numpy as np
import pytest

from app.core.backend import BaseBackend, OutOfMemoryError
from app.core.choice import generate_choice
from app.core.constants import DEFAULT_TILE_PX, RGB_CHANNELS
from app.core.params import MosaicParams
from app.core.result import COMPARED_STAGES, Stage
from app.core.timing import PerfCounterTimer
from tests.conftest import random_target, random_tiles

MATCH_BLOCKS = 10
ROWS, COLS, N_TILES = 2, 3, 4


class FakeBackend(BaseBackend):
  """Backend falso que registra el orden de los pasos."""

  name = "fake"

  def __init__(self, fail_matching: bool = False) -> None:
    super().__init__("fake device")
    self.calls: list[str] = []
    self.fail_matching = fail_matching

  def _warmup(self) -> None:
    self.calls.append("warmup")

  def _create_timer(self):
    return PerfCounterTimer()

  def _prepare_tiles(self, job, report):
    self.calls.append(Stage.PREPARE_TILES)

  def _target_descriptors(self, job, report):
    self.calls.append(Stage.TARGET_DESCRIPTORS)

  def _match(self, job, report):
    self.calls.append(Stage.MATCHING)
    if self.fail_matching:
      raise MemoryError
    for block in range(MATCH_BLOCKS):
      report((block + 1) / MATCH_BLOCKS)
    job.buffers["topk"] = np.zeros((job.n_cells, job.params.k), dtype=np.int32)

  def _compose(self, job, report):
    self.calls.append(Stage.COMPOSE)

  def _download(self, job, timer):
    return np.zeros(job.output_shape, dtype=np.uint8)

  def _collect_topk(self, job):
    topk = job.buffers["topk"]
    return topk, topk.astype(np.float32)


def run_fake(backend: FakeBackend, on_progress=None):
  params = MosaicParams(cols=COLS, k=2)
  choice = generate_choice(params.seed, params.k, ROWS * COLS)
  return backend.run(random_tiles(N_TILES), random_target(ROWS, COLS), params, choice, on_progress)


def test_run_warms_up_then_executes_stages_in_order():
  backend = FakeBackend()
  run_fake(backend)
  assert backend.calls == ["warmup", *COMPARED_STAGES]


def test_progress_reports_start_end_and_each_matching_block():
  events = []
  run_fake(FakeBackend(), lambda stage, fraction: events.append((stage, fraction)))
  matching = [fraction for stage, fraction in events if stage == Stage.MATCHING.value]
  assert len(matching) >= MATCH_BLOCKS
  assert matching == sorted(matching) and matching[0] == 0.0 and matching[-1] == 1.0
  assert [stage for stage, fraction in events if fraction == 0.0] == [stage.value for stage in COMPARED_STAGES]


def test_result_has_expected_structure_and_consistent_timings():
  result = run_fake(FakeBackend())
  assert result.image.shape == (ROWS * DEFAULT_TILE_PX, COLS * DEFAULT_TILE_PX, RGB_CHANNELS)
  assert result.topk_idx.shape == (ROWS * COLS, 2)
  assert result.timings.total_ms >= result.timings.stages_sum_ms()
  assert (result.backend_name, result.device_name) == ("fake", "fake device")


def test_memory_error_is_reported_and_backend_stays_usable():
  backend = FakeBackend(fail_matching=True)
  with pytest.raises(OutOfMemoryError, match="memoria insuficiente"):
    run_fake(backend)
  backend.fail_matching = False
  assert run_fake(backend).image.dtype == np.uint8
