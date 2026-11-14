"""Registro de backends con fábricas falsas: detección, aislamiento de fallas y selección."""

import logging

import pytest

from app.backends.gpu_base import REASON_KERNEL_BUILD, REASON_NO_CUDA_DEVICES, REASON_NO_OPENCL_GPU
from app.backends.registry import (
  CPU,
  CUDA,
  OPENCL,
  REASON_DRIVER,
  REASON_NO_GPU,
  REASON_NOT_INSTALLED,
  BackendRegistry,
  BackendUnavailableError,
  main,
)
from app.core.backend import BackendInitError

BUILD_LOG = "mosaic.cl:12:3: error: use of undeclared identifier 'DESC_DIMM'"
RTX = "GeForce RTX 3060"


class FakeBackend:
  """Backend mínimo: nombre, dispositivo, warmup y close."""

  def __init__(self, name: str, device_name: str) -> None:
    self.name, self.device_name, self.init_ms = name, device_name, None
    self.closed = False

  def warmup(self) -> float:
    self.init_ms = 1.0
    return self.init_ms

  def close(self) -> None:
    self.closed = True


def working(name: str, device: str = RTX):
  return lambda: FakeBackend(name, device)


def failing(error: Exception):
  def factory():
    raise error

  return factory


def registry_with(cuda, opencl) -> BackendRegistry:
  registry = BackendRegistry({CPU: working(CPU, "CPU"), CUDA: cuda, OPENCL: opencl})
  registry.detect_and_warmup()
  return registry


def test_without_gpu_libraries_only_cpu_is_available():
  missing = failing(ModuleNotFoundError("No module named 'pycuda'"))
  registry = registry_with(missing, failing(ModuleNotFoundError("No module named 'pyopencl'")))
  assert [status.available for status in registry.statuses()] == [True, False, False]
  assert registry.status(CUDA).reason == registry.status(OPENCL).reason == REASON_NOT_INSTALLED
  assert registry.status(CPU).describe().startswith("CPU secuencial: siempre disponible")


def test_cuda_driver_without_devices():
  registry = registry_with(failing(BackendInitError(REASON_NO_CUDA_DEVICES)), working(OPENCL))
  assert registry.status(CUDA).describe() == "CUDA: no disponible (sin dispositivos CUDA)"


def test_opencl_build_failure_is_isolated_and_logged_completely(caplog):
  with caplog.at_level(logging.ERROR):
    registry = registry_with(working(CUDA), failing(BackendInitError(REASON_KERNEL_BUILD, BUILD_LOG)))
  assert registry.status(OPENCL).describe() == f"OpenCL: no disponible ({REASON_KERNEL_BUILD})"
  assert BUILD_LOG in caplog.text
  assert registry.status(CUDA).available and registry.status(CPU).available


def test_unexpected_errors_are_driver_errors_and_close_the_backend():
  backend = FakeBackend(OPENCL, RTX)
  backend.warmup = failing(RuntimeError("clGetPlatformIDs failed"))
  registry = registry_with(working(CUDA), lambda: backend)
  assert registry.status(OPENCL).reason == REASON_DRIVER and backend.closed


def test_requested_cpu_runs_on_cpu_even_with_gpu_available():
  registry = registry_with(working(CUDA), working(OPENCL))
  (backend,) = registry.resolve([CPU])
  assert backend.name == CPU


def test_requested_unavailable_backend_is_rejected_with_its_reason():
  registry = registry_with(working(CUDA), failing(BackendInitError(REASON_NO_OPENCL_GPU)))
  with pytest.raises(BackendUnavailableError, match=REASON_NO_OPENCL_GPU):
    registry.resolve([OPENCL])


def test_unknown_backend_is_rejected():
  with pytest.raises(BackendUnavailableError, match="desconocido"):
    registry_with(working(CUDA), working(OPENCL)).resolve(["metal"])


def test_preferred_gpu_is_cuda_when_both_are_available():
  preference = registry_with(working(CUDA), working(OPENCL)).preferred_gpu()
  assert preference.status.name == CUDA and preference.status.device_name == RTX


def test_preferred_gpu_is_opencl_without_cuda():
  preference = registry_with(failing(ModuleNotFoundError("pycuda")), working(OPENCL, "Radeon RX 7600")).preferred_gpu()
  assert preference.status.name == OPENCL and preference.status.device_name == "Radeon RX 7600"


def test_no_preferred_gpu_combines_both_reasons():
  registry = registry_with(failing(ModuleNotFoundError("pycuda")), failing(BackendInitError(REASON_NO_OPENCL_GPU)))
  preference = registry.preferred_gpu()
  assert preference.status is None
  assert preference.reason == f"{REASON_NO_GPU} (CUDA: {REASON_NOT_INSTALLED}; OpenCL: {REASON_NO_OPENCL_GPU})"


def test_close_releases_every_created_backend():
  backends = {}

  def remember(name):
    def factory():
      backends[name] = FakeBackend(name, RTX)
      return backends[name]

    return factory

  with BackendRegistry({CUDA: remember(CUDA), OPENCL: remember(OPENCL)}) as registry:
    registry.detect_and_warmup()
  assert all(backend.closed for backend in backends.values())


def test_diagnostic_prints_every_backend(monkeypatch, capsys):
  monkeypatch.setattr(
    "app.backends.registry.DEFAULT_FACTORIES",
    {CPU: working(CPU, "CPU"), CUDA: failing(ModuleNotFoundError("pycuda")), OPENCL: working(OPENCL, "Apple M2")},
  )
  main()
  output = capsys.readouterr().out
  assert "CUDA: no disponible (biblioteca no instalada)" in output
  assert "OpenCL: Apple M2" in output and "GPU preferida: OpenCL: Apple M2" in output
