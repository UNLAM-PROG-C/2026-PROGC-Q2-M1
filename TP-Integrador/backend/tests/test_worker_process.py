"""Integración: el worker real, solo con CPU, en un proceso spawn."""

import multiprocessing
import queue
import time

from PIL import Image

from app.core.params import MosaicParams
from app.worker.main import WorkerOptions, worker_main
from app.worker.messages import BackendFinished, JobFinished, JobRejected, RunJob, Shutdown, WorkerReady
from tests.conftest import write_random_images

# El warmup de CPU compila con Numba: el arranque puede tardar decenas de segundos.
EVENT_TIMEOUT_S = 180.0
SHUTDOWN_TIMEOUT_S = 60.0
DECODE_PROCESSES = 2
N_TILES = 12
COLS = 6


def wait_for(events, kind: type):
  deadline = time.monotonic() + EVENT_TIMEOUT_S
  while time.monotonic() < deadline:
    try:
      event = events.get(timeout=1.0)
    except queue.Empty:
      continue
    if isinstance(event, kind):
      return event
  raise AssertionError(f"no llegó {kind.__name__}")


def make_job(tmp_path, job_id: str) -> RunJob:
  write_random_images(tmp_path / "tiles", [f"sub/t{i:02d}.png" for i in range(N_TILES)])
  Image.new("RGB", (64, 32), (200, 30, 30)).save(tmp_path / "target.png")
  params = MosaicParams(cols=COLS, tile_px=16, k=3, alpha=0.5, seed=1)
  return RunJob(job_id, str(tmp_path / "tiles"), str(tmp_path / "target.png"), params, ("cpu",), str(tmp_path / job_id))


def test_real_worker_runs_a_job_rejects_a_concurrent_one_and_shuts_down(tmp_path):
  context = multiprocessing.get_context("spawn")
  command_q, event_q = context.Queue(), context.Queue()
  options = WorkerOptions(decode_processes=DECODE_PROCESSES, backends=("cpu",))
  process = context.Process(target=worker_main, args=(command_q, event_q, options))
  process.start()
  try:
    ready = wait_for(event_q, WorkerReady)
    assert [status.name for status in ready.statuses] == ["cpu"]
    assert ready.preferred_gpu.status is None and ready.calibration is not None
    command_q.put(make_job(tmp_path, "first"))
    command_q.put(make_job(tmp_path, "second"))
    assert wait_for(event_q, JobRejected).job_id == "second"
    finished = wait_for(event_q, BackendFinished)
    assert finished.job_id == "first" and (finished.width, finished.height) == (COLS * 16, 3 * 16)
    assert wait_for(event_q, JobFinished).job_id == "first"
  finally:
    command_q.put(Shutdown())
    process.join(SHUTDOWN_TIMEOUT_S)
  assert process.exitcode == 0
  assert not multiprocessing.active_children()
