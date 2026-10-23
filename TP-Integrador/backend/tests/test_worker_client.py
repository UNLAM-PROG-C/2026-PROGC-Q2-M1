import multiprocessing
import queue
import time

from app.core.params import MosaicParams
from app.web.worker_client import WorkerClient
from app.worker.main import WorkerOptions
from app.worker.messages import JobFinished, RunJob, WorkerCrashed, WorkerReady
from tests.fake_worker import CRASH_EXIT_CODE, CRASH_JOB_ID, fake_worker_main, stubborn_worker_main

EVENT_TIMEOUT_S = 60.0
SHORT_SHUTDOWN_S = 1.0


def wait_for(events: queue.Queue, kind: type):
  deadline = time.monotonic() + EVENT_TIMEOUT_S
  while time.monotonic() < deadline:
    event = events.get(timeout=EVENT_TIMEOUT_S)
    if isinstance(event, kind):
      return event
  raise AssertionError(f"no llegó {kind.__name__}")


def job(job_id: str) -> RunJob:
  return RunJob(job_id, "tiles", "target.jpg", MosaicParams(cols=4), ("cpu",), "out")


def test_crashed_worker_is_reported_and_relaunched():
  events = queue.Queue()
  client = WorkerClient(events.put, WorkerOptions(), EVENT_TIMEOUT_S, target=fake_worker_main)
  client.start()
  try:
    wait_for(events, WorkerReady)
    first_pid = client.pid
    client.send(job(CRASH_JOB_ID))
    assert wait_for(events, WorkerCrashed).exitcode == CRASH_EXIT_CODE
    wait_for(events, WorkerReady)
    assert client.pid != first_pid
    client.send(job("ok"))
    assert wait_for(events, JobFinished).job_id == "ok"
  finally:
    client.stop()
  assert not multiprocessing.active_children()


def test_stop_terminates_a_worker_that_ignores_shutdown():
  events = queue.Queue()
  client = WorkerClient(events.put, WorkerOptions(), SHORT_SHUTDOWN_S, target=stubborn_worker_main)
  client.start()
  wait_for(events, WorkerReady)
  start = time.monotonic()
  client.stop()
  assert time.monotonic() - start < EVENT_TIMEOUT_S
  assert not multiprocessing.active_children()
  assert all(not isinstance(event, WorkerCrashed) for event in list(events.queue))
