import dataclasses
import pickle
import typing

import numpy as np
import pytest

from app.backends.cpu.calibration import CpuCalibration
from app.backends.registry import BackendStatus, GpuPreference
from app.core.params import MosaicParams
from app.core.result import StageTimings
from app.core.verification import CellDifferences, VerificationSummary
from app.worker import messages

TIMINGS = StageTimings(1.0, 2.0, 3.0, 4.0, 10.0, transfer_h2d_ms=0.5)
CPU_STATUS = BackendStatus("cpu", True, "CPU", init_ms=12.0)
CUDA_STATUS = BackendStatus("cuda", True, "RTX", init_ms=5.0, warnings=("fma",))

SAMPLES = [
  messages.RunJob("j1", "/tmp/tiles", "/tmp/target.jpg", MosaicParams(cols=10, k=3), ("cpu", "cuda"), "/tmp/out"),
  messages.Shutdown(),
  messages.WorkerReady((CPU_STATUS, CUDA_STATUS), GpuPreference(CUDA_STATUS), CpuCalibration(1.0, 2.0, 3.0)),
  messages.WorkerReady((CPU_STATUS,), GpuPreference(None, "no se detectó una GPU compatible"), None),
  messages.JobProgress("j1", None, messages.STAGE_LOAD, 0.0),
  messages.LoadFinished("j1", 12.5, False, 200, 3, 60, 80, 4800),
  messages.BackendFinished("j1", "cuda", "RTX", TIMINGS, 5.0, "a.png", "a.jpg", "p.jpg", 2560, 1920),
  messages.BackendFailed("j1", "cuda", "memoria insuficiente en el dispositivo"),
  messages.ComparisonFinished("j1", VerificationSummary("cpu", {"opencl": CellDifferences(3, 0, 3)})),
  messages.JobFinished("j1"),
  messages.JobFailed("j1", "memoria insuficiente en el dispositivo"),
  messages.JobRejected("j2", "ya hay un trabajo en curso"),
  messages.WorkerCrashed(1),
]


@pytest.mark.parametrize("message", SAMPLES, ids=lambda message: type(message).__name__)
def test_message_survives_pickle_round_trip(message):
  assert pickle.loads(pickle.dumps(message)) == message


def _all_message_classes():
  return [
    value
    for value in vars(messages).values()
    if dataclasses.is_dataclass(value) and value.__module__ == messages.__name__
  ]


def _mentions_ndarray(hint) -> bool:
  if hint is np.ndarray:
    return True
  return any(_mentions_ndarray(argument) for argument in typing.get_args(hint))


def test_every_message_class_is_covered_by_a_sample():
  assert {type(sample) for sample in SAMPLES} == set(_all_message_classes())


@pytest.mark.parametrize("message_class", _all_message_classes(), ids=lambda cls: cls.__name__)
def test_no_message_has_array_fields(message_class):
  hints = typing.get_type_hints(message_class)
  assert not any(_mentions_ndarray(hint) for hint in hints.values())
  assert message_class.__dataclass_params__.frozen
