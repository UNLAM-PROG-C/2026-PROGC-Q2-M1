"""Backend OpenCL: selección de dispositivo, memoria del matching, transferencias medidas."""

import importlib.util
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from app.backends.gpu_base import matching_chunk_rows
from app.backends.opencl import backend as opencl_module
from app.backends.opencl.device import display_name, select_gpu
from app.backends.opencl.timing import OpenClProfilingTimer, span_ms
from app.core.backend import BackendInitError
from app.core.constants import FLOAT32_BYTES
from app.core.result import Stage
from tests.conftest import END_OF_MEASUREMENT, mark_end_of_measurement, require_backend, spy
from tests.test_gpu_backends import small_job

GPU, CPU_TYPE = 4, 2
NVIDIA_VENDOR, AMD_VENDOR, INTEL_VENDOR = "NVIDIA Corporation", "Advanced Micro Devices, Inc.", "Intel(R) Corporation"
N_TILES_FOR_ROWS = 1000
NS = 1_000_000


class FakeDevice(SimpleNamespace):
  """Dispositivo con la forma de ``pyopencl.Device``."""


class FakePlatform:
  """Plataforma con la forma de ``pyopencl.Platform``."""

  def __init__(self, *devices: FakeDevice) -> None:
    self._devices = list(devices)

  def get_devices(self):
    if not self._devices:
      raise LookupError("DEVICE_NOT_FOUND")
    return self._devices


def gpu(name: str, vendor: str) -> FakeDevice:
  return FakeDevice(name=name, vendor=vendor, type=GPU)


# --- Selección de dispositivo (funciones puras) ---------------------------------------


def test_amd_is_preferred_over_nvidia():
  nvidia, amd = gpu("GeForce RTX 3060", NVIDIA_VENDOR), gpu("Radeon RX 7600", AMD_VENDOR)
  assert select_gpu([FakePlatform(nvidia), FakePlatform(amd)], GPU) is amd


def test_only_nvidia_is_selected():
  nvidia = gpu("GeForce RTX 3060", NVIDIA_VENDOR)
  assert select_gpu([FakePlatform(), FakePlatform(nvidia)], GPU, (LookupError,)) is nvidia


def test_only_cpu_devices_means_no_gpu():
  cpu = FakeDevice(name="Ryzen", vendor=AMD_VENDOR, type=CPU_TYPE)
  assert select_gpu([FakePlatform(cpu)], GPU) is None


def test_first_non_amd_gpu_in_platform_order():
  intel, nvidia = gpu("Iris Xe", INTEL_VENDOR), gpu("GeForce", NVIDIA_VENDOR)
  assert select_gpu([FakePlatform(intel, nvidia)], GPU) is intel


def test_name_filter_overrides_amd_priority():
  nvidia, amd = gpu("GeForce RTX 2080", NVIDIA_VENDOR), gpu("gfx1036", AMD_VENDOR)
  assert select_gpu([FakePlatform(nvidia), FakePlatform(amd)], GPU, name_filter="nvidia") is nvidia


def test_amd_display_name_uses_board_name():
  amd = FakeDevice(name="gfx1036", vendor=AMD_VENDOR, type=GPU, board_name_amd="AMD Radeon(TM) Graphics")
  assert display_name(amd) == "AMD Radeon(TM) Graphics (gfx1036)"


def test_backend_without_gpu_reports_reason(monkeypatch):
  cpu = FakeDevice(name="Ryzen", vendor=AMD_VENDOR, type=CPU_TYPE)
  fake_cl = SimpleNamespace(
    get_platforms=lambda: [FakePlatform(cpu)], device_type=SimpleNamespace(GPU=GPU), Error=LookupError
  )
  monkeypatch.setattr(opencl_module, "_load_opencl", lambda: fake_cl)
  with pytest.raises(BackendInitError) as raised:
    opencl_module.OpenClBackend()
  assert raised.value.reason == "sin GPU OpenCL"


def test_module_imports_without_pyopencl(monkeypatch):
  monkeypatch.setitem(sys.modules, "pyopencl", None)
  spec = importlib.util.spec_from_file_location("opencl_backend_copy", opencl_module.__file__)
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  with pytest.raises(ImportError):
    module.OpenClBackend()


# --- Memoria del matching ---------------------------------------------------------------


def test_chunk_is_bounded_by_max_single_allocation():
  row_bytes = N_TILES_FOR_ROWS * FLOAT32_BYTES
  rows = matching_chunk_rows(50_000 * row_bytes, N_TILES_FOR_ROWS, 100_000, max_alloc_bytes=20_000 * row_bytes)
  assert rows <= 20_000


def test_available_bytes_use_amd_free_memory_when_present():
  assert opencl_module.opencl_available_bytes(1000, 400, 100, 0.5) == 100
  assert opencl_module.opencl_available_bytes(1000, None, 100, 0.5) == 400


# --- Profiling -----------------------------------------------------------------------------


def test_profiling_span_goes_from_first_start_to_last_end():
  events = [
    SimpleNamespace(profile=SimpleNamespace(start=2 * NS, end=3 * NS)),
    SimpleNamespace(profile=SimpleNamespace(start=4 * NS, end=7 * NS)),
  ]
  timer = OpenClProfilingTimer()
  timer.start(Stage.MATCHING)
  for event in events:
    timer.add(event)
  timer.stop(Stage.MATCHING)
  timer.add(events[0])  # fuera de una etapa: no se cuenta
  assert timer.elapsed_ms() == {Stage.MATCHING: span_ms(events)} and span_ms(events) == pytest.approx(5.0)


# --- Con una GPU OpenCL real -------------------------------------------------------------------


def test_only_inputs_go_up_and_only_the_image_comes_down_inside_measurement(backend_registry, monkeypatch):
  backend = require_backend(backend_registry, "opencl")
  tiles, target, params, choice = small_job()
  backend.run(tiles, target, params, choice)  # deja los staging con el tamaño de este trabajo
  log: list[tuple] = []
  describe = lambda queue, dest, src, **kwargs: (dest, src, kwargs.get("byte_count"))  # noqa: E731
  spy(monkeypatch, backend._cl, "enqueue_copy", log, describe)
  mark_end_of_measurement(monkeypatch, log)
  result = backend.run(tiles, target, params, choice)
  end, staging = log.index(END_OF_MEASUREMENT), backend._staging
  measured = log[:end]
  assert [size for _, src, size in measured if src is staging["input"]] == [tiles.nbytes, target.nbytes, choice.nbytes]
  assert [size for dest, _, size in measured if dest is staging["output"]] == [result.image.nbytes]
  assert len(measured) == len(("tiles_src", "target_src", "choice", "image"))
  assert all(isinstance(dest, np.ndarray) for dest, _, _ in log[end + 1 :])
