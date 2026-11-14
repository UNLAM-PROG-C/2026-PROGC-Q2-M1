"""Propiedades comunes de los backends CUDA y OpenCL (se saltean si no están disponibles)."""

import numpy as np
import pytest

from app.backends.registry import CUDA, OPENCL
from app.core.backend import OutOfMemoryError
from app.core.choice import generate_choice
from app.core.constants import DEFAULT_TILE_PX, RGB_CHANNELS
from app.core.params import MosaicParams
from app.core.result import COMPARED_STAGES, Stage
from tests.conftest import blocky_tiles, random_target, require_backend

GPU_BACKENDS = (CUDA, OPENCL)
ROWS, COLS, N_TILES = 8, 12, 64
SMALL_CHUNK = 16
# Filas imposibles para la matriz de distancias: N · 4 B · 1e10 son cientos de GB.
IMPOSSIBLE_CHUNK_ROWS = 10**10


def small_job(k: int = 4):
  params = MosaicParams(cols=COLS, k=k, alpha=0.7)
  choice = generate_choice(params.seed, params.k, ROWS * COLS)
  return blocky_tiles(N_TILES), random_target(ROWS, COLS), params, choice


@pytest.mark.parametrize("backend_name", GPU_BACKENDS)
def test_stage_times_are_positive_and_within_wall_clock_total(backend_registry, backend_name):
  backend = require_backend(backend_registry, backend_name)
  timings = backend.run(*small_job()).timings
  for stage in COMPARED_STAGES:
    assert getattr(timings, f"{stage.value}_ms") > 0
  assert timings.transfer_h2d_ms > 0 and timings.transfer_d2h_ms > 0
  assert timings.staging_h2d_ms is not None and timings.staging_d2h_ms is not None
  assert timings.stages_sum_ms() <= timings.total_ms


@pytest.mark.parametrize("backend_name", GPU_BACKENDS)
def test_progress_is_reported_per_matching_block_in_order(backend_registry, monkeypatch, backend_name):
  backend = require_backend(backend_registry, backend_name)
  monkeypatch.setattr(backend, "chunk_cells", SMALL_CHUNK)
  events = []
  backend.run(*small_job(), lambda stage, fraction: events.append((stage, fraction)))
  matching = [fraction for stage, fraction in events if stage == Stage.MATCHING.value]
  assert len(matching) >= ROWS * COLS // SMALL_CHUNK
  assert matching == sorted(matching) and matching[-1] == 1.0
  assert [stage for stage, fraction in events if fraction == 0.0] == [stage.value for stage in COMPARED_STAGES]


@pytest.mark.parametrize("backend_name", GPU_BACKENDS)
def test_impossible_chunk_fails_with_out_of_memory_and_backend_stays_usable(
  backend_registry, monkeypatch, backend_name
):
  backend = require_backend(backend_registry, backend_name)
  monkeypatch.setattr(backend, "_chunk_rows", lambda job: IMPOSSIBLE_CHUNK_ROWS)
  with pytest.raises(OutOfMemoryError, match="memoria insuficiente"):
    backend.run(*small_job())
  monkeypatch.undo()
  result = backend.run(*small_job())
  assert result.image.shape == (ROWS * DEFAULT_TILE_PX, COLS * DEFAULT_TILE_PX, RGB_CHANNELS)


@pytest.mark.parametrize("backend_name", GPU_BACKENDS)
def test_repeated_runs_are_reproducible(backend_registry, backend_name):
  backend = require_backend(backend_registry, backend_name)
  first, second = backend.run(*small_job()), backend.run(*small_job())
  np.testing.assert_array_equal(first.topk_idx, second.topk_idx)
  np.testing.assert_array_equal(first.image, second.image)
  assert first.backend_name == backend_name and first.device_name == backend.device_name
