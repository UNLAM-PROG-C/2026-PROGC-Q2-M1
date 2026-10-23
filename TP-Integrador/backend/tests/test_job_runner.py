import queue

import numpy as np
from PIL import Image

from app.core.backend import OutOfMemoryError
from app.core.constants import CELL_PX, RGB_CHANNELS
from app.core.params import MosaicParams
from app.core.result import MosaicResult, StageTimings
from app.loading.cache import LoadResult
from app.loading.target_loader import TargetImage
from app.loading.tile_loader import TileBatch
from app.worker import job_runner
from app.worker.job_runner import JobRunner, ThrottledProgress
from app.worker.messages import BackendFinished, JobFailed, JobFinished, JobProgress, LoadFinished, RunJob
from tests.conftest import random_target, random_tiles

ROWS, COLS, N_TILES = 3, 4, 3
PREVIEW_SIDE = 64
TIMINGS = StageTimings(1.0, 2.0, 3.0, 4.0, 10.0)


class FakeLoader:
  def load(self, tiles_root, target_path, cols):
    tiles = TileBatch(random_tiles(N_TILES), tuple(f"t{i}.jpg" for i in range(N_TILES)), ("roto.jpg",))
    target = TargetImage(random_target(ROWS, cols), ROWS, cols)
    return LoadResult(tiles, target, 5.0, 1.0, False, False)


class FakeBackend:
  name = "cpu"
  device_name = "falso"
  init_ms = 7.0

  def __init__(self, error: Exception | None = None):
    self.error = error
    self.calls = []

  def run(self, tiles_src, target_src, params, choice, on_progress=None):
    self.calls.append(params)
    for stage in ("prepare_tiles", "matching"):
      on_progress(stage, 0.0)
      on_progress(stage, 1.0)
    if self.error:
      raise self.error
    rows = target_src.shape[0] // CELL_PX
    image = np.zeros((rows * params.tile_px, params.cols * params.tile_px, RGB_CHANNELS), dtype=np.uint8)
    return MosaicResult(image, np.zeros((1, 1)), np.zeros((1, 1)), TIMINGS, self.name, self.device_name)


class FakeRegistry:
  def __init__(self, backend):
    self.backend = backend

  def resolve(self, names):
    return [self.backend for _ in names]


def run_job(tmp_path, backend):
  events = queue.Queue()
  command = RunJob(
    "j1",
    str(tmp_path / "tiles"),
    str(tmp_path / "t.jpg"),
    MosaicParams(cols=COLS, tile_px=16, k=5),
    ("cpu",),
    str(tmp_path / "out"),
  )
  JobRunner(FakeLoader(), FakeRegistry(backend), events, PREVIEW_SIDE).run(command)
  return [events.get_nowait() for _ in range(events.qsize())]


def test_successful_job_event_sequence(tmp_path):
  backend = FakeBackend()
  events = run_job(tmp_path, backend)
  kinds = [type(event) for event in events]
  assert kinds[0] is JobProgress and events[0].stage == "load" and events[0].backend is None
  assert kinds.index(LoadFinished) < kinds.index(BackendFinished) < kinds.index(JobFinished) == len(events) - 1
  load = next(event for event in events if isinstance(event, LoadFinished))
  assert (load.n_tiles, load.skipped_files, load.rows, load.cols, load.m_cells) == (N_TILES, 1, ROWS, COLS, ROWS * COLS)
  stages = [event.stage for event in events if isinstance(event, JobProgress)]
  assert stages.index("matching") < stages.index("save")
  assert backend.calls[0].k == N_TILES  # k se acota a las teselas válidas


def test_results_are_saved_after_backend_with_preview(tmp_path):
  finished = next(event for event in run_job(tmp_path, FakeBackend()) if isinstance(event, BackendFinished))
  assert (finished.width, finished.height, finished.init_ms) == (COLS * 16, ROWS * 16, 7.0)
  with Image.open(finished.png_path) as png, Image.open(finished.preview_path) as preview:
    assert png.size == (COLS * 16, ROWS * 16)
    assert max(preview.size) <= PREVIEW_SIDE
  assert finished.jpeg_path.endswith(".jpg")


def test_failing_job_reports_readable_reason(tmp_path):
  events = run_job(tmp_path, FakeBackend(OutOfMemoryError("sin memoria")))
  assert isinstance(events[-1], JobFailed)
  assert events[-1].reason == "memoria insuficiente en el dispositivo"
  assert not any(isinstance(event, JobFinished | BackendFinished) for event in events)


def test_progress_is_throttled_but_keeps_stage_changes_and_ends(monkeypatch):
  events, now = queue.Queue(), [0.0]
  progress = ThrottledProgress(events, "j1", "cpu", clock=lambda: now[0])
  for fraction in (0.0, 0.1, 0.2, 0.3):
    progress("matching", fraction)
  progress("matching", 1.0)
  now[0] = job_runner.PROGRESS_MIN_INTERVAL_MS / 1000.0
  progress("compose", 0.0)
  sent = [(event.stage, event.fraction) for event in (events.get_nowait() for _ in range(events.qsize()))]
  assert sent == [("matching", 0.0), ("matching", 1.0), ("compose", 0.0)]
