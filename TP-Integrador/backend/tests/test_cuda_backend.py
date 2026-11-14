"""Backend CUDA: import diferido, transferencias medidas, memoria pinned y cierre."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.backends.cuda import backend as cuda_module
from app.backends.gpu_base import NOTE_PAGEABLE_TRANSFER
from app.backends.registry import CUDA, REASON_NOT_INSTALLED, BackendRegistry, _create_cuda
from app.core.backend import BackendInitError
from tests.conftest import END_OF_MEASUREMENT, mark_end_of_measurement, require_backend, spy
from tests.test_gpu_backends import small_job

BACKEND_DIR = Path(__file__).resolve().parents[1]
CLOSE_SCRIPT = (
  "from app.backends.cuda.backend import CudaBackend\nb = CudaBackend()\nb.warmup()\nb.close()\nb.close()\n"
)
CLOSE_TIMEOUT_SECONDS = 120


def test_module_imports_without_pycuda(monkeypatch):
  monkeypatch.setitem(sys.modules, "pycuda", None)
  monkeypatch.setitem(sys.modules, "pycuda.driver", None)
  spec = importlib.util.spec_from_file_location("cuda_backend_copy", cuda_module.__file__)
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  with pytest.raises(ImportError):
    module.CudaBackend()


def test_registry_reports_missing_library(monkeypatch):
  monkeypatch.setitem(sys.modules, "pycuda", None)
  monkeypatch.setitem(sys.modules, "pycuda.driver", None)
  (status,) = BackendRegistry({CUDA: _create_cuda}).detect_and_warmup()
  assert not status.available and status.reason == REASON_NOT_INSTALLED


def test_driver_without_devices_is_reported(monkeypatch):
  fake_driver = SimpleNamespace(Device=SimpleNamespace(count=lambda: 0))
  monkeypatch.setattr(cuda_module, "_load_driver", lambda: fake_driver)
  with pytest.raises(BackendInitError) as raised:
    cuda_module.CudaBackend()
  assert raised.value.reason == "sin dispositivos CUDA"


def spy_copies(monkeypatch, drv) -> list[tuple]:
  """Registra las copias async y el momento en que se cierra la medición."""
  log: list[tuple] = []
  spy(monkeypatch, drv, "memcpy_htod_async", log, lambda dst, src, stream=None: ("h2d", src.nbytes))
  spy(monkeypatch, drv, "memcpy_dtoh_async", log, lambda dst, src, stream=None: ("d2h", dst.nbytes))
  mark_end_of_measurement(monkeypatch, log)
  return log


def test_only_inputs_go_up_and_only_the_image_comes_down_inside_measurement(backend_registry, monkeypatch):
  backend = require_backend(backend_registry, CUDA)
  tiles, target, params, choice = small_job()
  log = spy_copies(monkeypatch, backend._drv)
  result = backend.run(tiles, target, params, choice)
  end = log.index(END_OF_MEASUREMENT)
  assert [entry for entry in log[:end] if entry[0] == "h2d"] == [
    ("h2d", tiles.nbytes),
    ("h2d", target.nbytes),
    ("h2d", choice.nbytes),
  ]
  assert [entry for entry in log[:end] if entry[0] == "d2h"] == [("d2h", result.image.nbytes)]
  assert sorted(log[end + 1 :]) == sorted([("d2h", result.topk_idx.nbytes), ("d2h", result.topk_dist.nbytes)])


def test_rejected_pinned_memory_falls_back_to_pageable(backend_registry, monkeypatch):
  backend = require_backend(backend_registry, CUDA)
  reference = backend.run(*small_job())

  def refuse_pinned(*args, **kwargs):
    raise MemoryError("page-locked rechazada (simulado)")

  monkeypatch.setattr(backend, "_staging", {})
  monkeypatch.setattr(backend._drv, "pagelocked_empty", refuse_pinned)
  result = backend.run(*small_job())
  assert NOTE_PAGEABLE_TRANSFER in result.notes
  np.testing.assert_array_equal(result.image, reference.image)
  assert NOTE_PAGEABLE_TRANSFER not in reference.notes


def test_context_is_released_without_driver_messages(backend_registry):
  require_backend(backend_registry, CUDA)
  completed = subprocess.run(
    [sys.executable, "-c", CLOSE_SCRIPT],
    cwd=BACKEND_DIR,
    capture_output=True,
    text=True,
    timeout=CLOSE_TIMEOUT_SECONDS,
    check=False,
  )
  assert completed.returncode == 0, completed.stderr
  assert "PyCUDA" not in completed.stderr and "error" not in completed.stderr.lower()
