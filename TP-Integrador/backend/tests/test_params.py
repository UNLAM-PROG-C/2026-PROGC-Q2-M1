"""Validación de parámetros, derivación de rows, choice y tiempos."""

import numpy as np
import pytest

from app.core.choice import generate_choice
from app.core.params import InvalidParamsError, MosaicParams, derive_rows
from app.core.result import NOT_APPLICABLE, StageTimings


def test_invalid_tile_px_lists_allowed_values():
  with pytest.raises(InvalidParamsError, match="16, 32, 64"):
    MosaicParams(cols=10, tile_px=48)


def test_k_greater_than_tiles_is_rejected():
  params = MosaicParams(cols=10, k=5)
  with pytest.raises(InvalidParamsError, match="k no puede superar N"):
    params.validate_for_batch(3)


@pytest.mark.parametrize("alpha", [-0.1, 1.5])
def test_alpha_out_of_range_is_rejected(alpha):
  with pytest.raises(InvalidParamsError, match="alpha"):
    MosaicParams(cols=10, alpha=alpha)


@pytest.mark.parametrize("kwargs", [{"cols": 0}, {"cols": 10, "k": 0}, {"cols": 10, "k": 17}, {"cols": 10, "seed": -1}])
def test_other_out_of_range_params_are_rejected(kwargs):
  with pytest.raises(InvalidParamsError):
    MosaicParams(**kwargs)


def test_defaults_are_valid():
  params = MosaicParams(cols=10)
  assert (params.tile_px, params.k, params.alpha) == (32, 5, 1.0)


def test_rows_for_4_3_target():
  assert derive_rows(100, 4000, 3000) == 75


def test_rows_for_very_wide_target_is_never_zero():
  assert derive_rows(10, 3000, 10) == 1


def test_choice_is_reproducible_by_seed():
  np.testing.assert_array_equal(generate_choice(42, 5, 1000), generate_choice(42, 5, 1000))


def test_choice_values_are_in_range():
  choice = generate_choice(7, 5, 1000)
  assert choice.dtype == np.int32
  assert choice.min() >= 0 and choice.max() < 5


def test_choice_with_k_one_is_all_zero():
  assert not generate_choice(42, 1, 1000).any()


def test_cpu_timings_report_transfers_as_not_applicable():
  timings = StageTimings(
    prepare_tiles_ms=1.0, target_descriptors_ms=2.0, matching_ms=3.0, compose_ms=4.0, total_ms=11.0
  )
  serialized = timings.to_dict()
  assert serialized["transfer_h2d_ms"] == NOT_APPLICABLE
  assert serialized["transfer_d2h_ms"] == NOT_APPLICABLE
  assert timings.stages_sum_ms() == pytest.approx(10.0)
