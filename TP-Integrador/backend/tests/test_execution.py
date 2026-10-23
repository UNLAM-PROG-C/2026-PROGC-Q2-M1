import pytest

from app.backends.registry import BackendRegistry, BackendStatus
from app.web.execution import ExecutionModeError, backends_for_mode, effective_k, execution_options
from app.worker.messages import WorkerReady

CPU = BackendStatus("cpu", True, "Ryzen", init_ms=1.0)


def ready_with(*statuses: BackendStatus) -> WorkerReady:
  registry = BackendRegistry({})
  registry._statuses = {status.name: status for status in statuses}  # Estados fijos, sin crear backends.
  return WorkerReady(statuses, registry.preferred_gpu(), None)


def test_cpu_mode_uses_cpu_backend():
  assert backends_for_mode("cpu", ready_with(CPU)) == ("cpu",)


def test_gpu_without_gpu_is_rejected_with_reason():
  ready = ready_with(
    CPU,
    BackendStatus("cuda", False, reason="biblioteca no instalada"),
    BackendStatus("opencl", False, reason="sin GPU OpenCL"),
  )
  with pytest.raises(ExecutionModeError, match="no se detectó una GPU compatible"):
    backends_for_mode("gpu", ready)
  options = execution_options(ready)
  assert options["gpu"]["available"] is False
  assert "no se detectó una GPU compatible" in options["gpu"]["reason"]
  assert options["cpu"] == {"available": True, "device": "Ryzen"}


def test_gpu_with_cuda_and_opencl_prefers_cuda():
  ready = ready_with(CPU, BackendStatus("cuda", True, "RTX 3060"), BackendStatus("opencl", True, "Radeon"))
  assert backends_for_mode("gpu", ready) == ("cuda",)
  assert execution_options(ready)["gpu"] == {"available": True, "api": "CUDA", "device": "RTX 3060", "reason": None}


def test_gpu_with_only_opencl_uses_opencl():
  ready = ready_with(
    CPU, BackendStatus("cuda", False, reason="sin dispositivos CUDA"), BackendStatus("opencl", True, "Radeon")
  )
  assert backends_for_mode("gpu", ready) == ("opencl",)
  assert execution_options(ready)["gpu"]["api"] == "OpenCL"


def test_unknown_mode_and_worker_not_ready_are_rejected():
  with pytest.raises(ExecutionModeError, match="desconocida"):
    backends_for_mode("both", ready_with(CPU))
  with pytest.raises(ExecutionModeError):
    backends_for_mode("cpu", None)
  assert execution_options(None)["cpu"]["available"] is False


def test_small_batch_bounds_k():
  assert effective_k(3) == 3
  assert effective_k(200) == 5
