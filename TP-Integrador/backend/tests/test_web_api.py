import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from starlette.websockets import WebSocketDisconnect

from app.backends.cpu.calibration import CpuCalibration
from app.backends.registry import BackendStatus, GpuPreference
from app.config import Settings
from app.core.result import StageTimings
from app.web.api import create_app
from app.worker.messages import BackendFinished, JobFinished, JobProgress, RunJob, WorkerCrashed, WorkerReady

ORIGIN = "http://127.0.0.1:5173"
OTHER_ORIGIN = "http://evil.example"
CUDA = BackendStatus("cuda", True, "RTX 2080", init_ms=3.0)
READY = WorkerReady(
  (BackendStatus("cpu", True, "Ryzen", init_ms=1.0), CUDA), GpuPreference(CUDA), CpuCalibration(1.0, 2.0, 3.0)
)
MAX_OUTPUT_PIXELS = 1_000_000


class FakeWorker:
  """Worker en memoria: guarda las órdenes y permite inyectar eventos."""

  def __init__(self, on_event):
    self.on_event = on_event
    self.sent = []
    self.stopped = False

  def start(self):
    self.on_event(READY)

  def send(self, command):
    self.sent.append(command)

  def stop(self):
    self.stopped = True


def image_bytes(size=(80, 60), image_format="PNG") -> bytes:
  buffer = io.BytesIO()
  Image.new("RGB", size, (90, 40, 200)).save(buffer, format=image_format)
  return buffer.getvalue()


@pytest.fixture
def api(tmp_path):
  workers = []

  def factory(on_event):
    workers.append(FakeWorker(on_event))
    return workers[-1]

  settings = Settings(temp_dir=tmp_path / "temp", max_output_pixels=MAX_OUTPUT_PIXELS, tile_sample_count=2)
  with TestClient(create_app(settings, factory)) as client:
    yield client, workers[0]
  assert workers[0].stopped


def upload_batch(client, count=3) -> dict:
  files = [("files", (f"t{i}.png", image_bytes(), "image/png")) for i in range(count)]
  files.append(("files", ("leeme.txt", b"x", "text/plain")))
  response = client.post("/api/tiles", files=files)
  assert response.status_code == 200, response.text
  return response.json()


def upload_target(client, size=(80, 60)) -> dict:
  response = client.post("/api/targets", files={"file": ("objetivo.png", image_bytes(size), "image/png")})
  assert response.status_code == 200, response.text
  return response.json()


def job_body(tiles, target, **overrides) -> dict:
  body = {
    "tiles_id": tiles["tiles_id"],
    "target_id": target["target_id"],
    "cols": 8,
    "tile_px": 16,
    "alpha": 0.6,
    "seed": 3,
    "mode": "gpu",
  }
  return {**body, **overrides}


def test_state_has_execution_options_rules_and_last_uploads(api):
  client, _ = api
  state = client.get("/api/state").json()
  assert state["worker"] == {"ready": True, "error": None}
  assert state["execution"]["gpu"] == {"available": True, "api": "CUDA", "device": "RTX 2080", "reason": None}
  assert state["calibration"] == {"matching_ns_per_pair": 1.0, "prepare_ns_per_pixel": 2.0, "compose_ns_per_pixel": 3.0}
  assert state["rules"]["cols"]["max"] == 400 and state["rules"]["max_output_pixels"] == MAX_OUTPUT_PIXELS
  assert state["last_tiles"] is None and state["job"] is None
  tiles, target = upload_batch(client), upload_target(client)
  state = client.get("/api/state").json()
  assert state["last_tiles"]["tiles_id"] == tiles["tiles_id"] and state["last_tiles"]["accepted"] == 3
  assert state["last_target"] == target


def test_uploads_and_their_files(api):
  client, _ = api
  tiles = upload_batch(client)
  assert (tiles["accepted"], tiles["ignored"], tiles["rejected"]) == (3, 1, 0)
  summary = client.get(f"/api/tiles/{tiles['tiles_id']}").json()
  assert summary["samples"] == ["t0.png", "t1.png"]
  assert client.get(f"/api/tiles/{tiles['tiles_id']}/samples/1").content == image_bytes()
  assert client.get(f"/api/tiles/{tiles['tiles_id']}/samples/2").status_code == 404
  target = upload_target(client, (120, 90))
  assert (target["width"], target["height"], target["filename"]) == (120, 90, "objetivo.png")
  assert client.get(f"/api/targets/{target['target_id']}/image").content == image_bytes((120, 90))
  gif = client.post("/api/targets", files={"file": ("a.gif", image_bytes(image_format="GIF"), "image/gif")})
  assert gif.status_code == 400 and "JPEG, PNG o WebP" in gif.json()["detail"]


def test_zip_upload_with_folders(api):
  client, _ = api
  buffer = io.BytesIO()
  with zipfile.ZipFile(buffer, "w") as archive:
    archive.writestr("a/1.jpg", image_bytes(image_format="JPEG"))
    archive.writestr("b/2.png", image_bytes())
    archive.writestr("../../etc/passwd", b"root")
  response = client.post("/api/tiles", files={"zip": ("lote.zip", buffer.getvalue(), "application/zip")})
  assert response.json()["accepted"] == 2 and response.json()["rejected"] == 1


def test_upload_declared_over_limit_is_413(tmp_path):
  settings = Settings(temp_dir=tmp_path / "temp", max_upload_mb=1)
  with TestClient(create_app(settings, FakeWorker)) as client:
    response = client.post("/api/targets", files={"file": ("t.png", bytes(2 * 1024 * 1024), "image/png")})
  assert response.status_code == 413


def test_job_is_accepted_and_sent_to_worker_with_bounded_k(api):
  client, worker = api
  tiles, target = upload_batch(client), upload_target(client)
  response = client.post("/api/jobs", json=job_body(tiles, target))
  assert response.status_code == 200, response.text
  assert response.json()["backends"] == ["cuda"]
  command = worker.sent[-1]
  assert isinstance(command, RunJob) and command.backends == ("cuda",)
  assert (command.params.k, command.params.alpha, command.params.cols) == (3, 0.6, 8)
  assert client.get("/api/state").json()["job"]["status"] == "running"


def test_second_job_while_running_is_409(api):
  client, _ = api
  tiles, target = upload_batch(client), upload_target(client)
  assert client.post("/api/jobs", json=job_body(tiles, target)).status_code == 200
  response = client.post("/api/jobs", json=job_body(tiles, target, mode="cpu"))
  assert response.status_code == 409
  assert response.json()["detail"] == "ya hay un trabajo en curso"


def test_job_with_huge_output_is_rejected_with_limit(api):
  client, worker = api
  tiles, target = upload_batch(client), upload_target(client)
  response = client.post("/api/jobs", json=job_body(tiles, target, cols=400, tile_px=64))
  assert response.status_code == 400
  assert str(MAX_OUTPUT_PIXELS) in response.json()["detail"]
  assert worker.sent == []


def test_invalid_params_and_missing_uploads(api):
  client, _ = api
  tiles, target = upload_batch(client), upload_target(client)
  assert client.post("/api/jobs", json=job_body(tiles, target, tile_px=20)).status_code == 400
  assert client.post("/api/jobs", json=job_body(tiles, target, mode="both")).status_code == 400
  assert client.post("/api/jobs", json=job_body(tiles, {"target_id": "nada"})).status_code == 404


def test_cors_only_for_frontend_origin(api):
  client, _ = api
  allowed = client.get("/api/state", headers={"Origin": ORIGIN})
  assert allowed.headers["access-control-allow-origin"] == ORIGIN
  other = client.options("/api/jobs", headers={"Origin": OTHER_ORIGIN, "Access-Control-Request-Method": "POST"})
  assert "access-control-allow-origin" not in other.headers
  assert "access-control-allow-origin" not in client.get("/api/state", headers={"Origin": OTHER_ORIGIN}).headers


def test_websocket_rejects_other_origin(api):
  client, _ = api
  with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws", headers={"Origin": OTHER_ORIGIN}) as ws:
    ws.receive_json()


def test_two_websocket_clients_receive_the_same_events(api):
  client, worker = api
  tiles, target = upload_batch(client), upload_target(client)
  with client.websocket_connect("/ws", headers={"Origin": ORIGIN}) as first, client.websocket_connect("/ws") as second:
    assert first.receive_json()["type"] == "state" and second.receive_json()["type"] == "state"
    job_id = client.post("/api/jobs", json=job_body(tiles, target)).json()["job_id"]
    worker.on_event(JobProgress(job_id, "cuda", "matching", 0.5))
    worker.on_event(JobFinished(job_id))
    for ws in (first, second):
      assert ws.receive_json()["type"] == "job_started"
      assert ws.receive_json() == {
        "type": "job_progress",
        "job_id": job_id,
        "backend": "cuda",
        "stage": "matching",
        "fraction": 0.5,
      }
      assert ws.receive_json() == {"type": "job_finished", "job_id": job_id}


def test_worker_crash_fails_running_job(api):
  client, worker = api
  tiles, target = upload_batch(client), upload_target(client)
  with client.websocket_connect("/ws") as ws:
    ws.receive_json()
    job_id = client.post("/api/jobs", json=job_body(tiles, target)).json()["job_id"]
    worker.on_event(WorkerCrashed(1))
    assert ws.receive_json()["type"] == "job_started"
    assert ws.receive_json() == {
      "type": "job_failed",
      "job_id": job_id,
      "reason": "el worker se detuvo inesperadamente",
    }
    assert ws.receive_json()["worker"]["ready"] is False
    assert ws.receive_json()["state"]["job"]["status"] == "failed"
    worker.on_event(READY)
    assert ws.receive_json()["worker"] == {"ready": True, "error": None}
  assert client.post("/api/jobs", json=job_body(tiles, target)).status_code == 200


def test_results_are_served_and_downloads_are_attachments(api, tmp_path):
  client, worker = api
  tiles, target = upload_batch(client), upload_target(client)
  job_id = client.post("/api/jobs", json=job_body(tiles, target)).json()["job_id"]
  paths = {kind: tmp_path / f"r.{kind}" for kind in ("png", "jpg", "preview")}
  for path in paths.values():
    path.write_bytes(b"data")
  timings = StageTimings(1.0, 2.0, 3.0, 4.0, 10.0, 0.5, 0.25)
  finished = BackendFinished(
    job_id, "cuda", "RTX", timings, 3.0, str(paths["png"]), str(paths["jpg"]), str(paths["preview"]), 128, 96
  )
  with client.websocket_connect("/ws") as ws:
    ws.receive_json()
    worker.on_event(finished)
    result = ws.receive_json()["result"]
  assert result["timings"]["staging_h2d_ms"] is None and result["timings"]["transfer_h2d_ms"] == 0.5
  png = client.get(f"/api/jobs/{job_id}/cuda/png")
  assert png.status_code == 200 and png.headers["content-disposition"].startswith("attachment")
  assert "attachment" not in client.get(f"/api/jobs/{job_id}/cuda/preview").headers.get("content-disposition", "")
  assert client.get(f"/api/jobs/{job_id}/cpu/png").status_code == 404
