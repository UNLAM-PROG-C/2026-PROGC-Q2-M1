"""Pipeline completo del backend CPU secuencial."""

import threading

import numba
import numpy as np
import pytest

from app.backends.cpu import stages
from app.backends.cpu.backend import CpuBackend, chunk_cells_for_budget
from app.core.choice import generate_choice
from app.core.constants import (
  CELL_PX,
  CPU_DISTANCE_BUDGET_BYTES,
  DEFAULT_K,
  DEFAULT_TILE_PX,
  FLOAT32_BYTES,
  RGB_CHANNELS,
)
from app.core.params import MosaicParams
from app.core.result import NOT_APPLICABLE, Stage
from tests.conftest import random_target, random_tiles, solid_tiles, target_from_cell_colors

COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 0, 0), (255, 255, 255)]
SMALL_CHUNK = 16
# Trabajo mediano para el test de un solo hilo: N = 300, M = 40·75 = 3.000.
MEDIUM_TILES, MEDIUM_ROWS, MEDIUM_COLS = 300, 40, 75
COMPILED_STAGES = (
  stages.resize_tiles,
  stages.tile_descriptors,
  stages.cell_descriptors,
  stages.sq_norms,
  stages.distances,
  stages.topk_rows,
  stages.compose,
)


def run_job(backend, tiles_src, target_src, params, on_progress=None):
  n_cells = target_src.shape[0] // CELL_PX * params.cols
  choice = generate_choice(params.seed, params.k, n_cells)
  return backend.run(tiles_src, target_src, params, choice, on_progress)


def test_solid_colors_are_assigned_to_matching_cells(cpu_backend):
  rng = np.random.default_rng(0)
  cell_color_idx = rng.integers(0, len(COLORS), (5, 7))
  target_src = target_from_cell_colors(np.asarray(COLORS)[cell_color_idx])
  result = run_job(cpu_backend, solid_tiles(COLORS), target_src, MosaicParams(cols=7, k=1, tile_px=16))
  np.testing.assert_array_equal(result.topk_idx[:, 0], cell_color_idx.reshape(-1))
  assert np.all(result.image[:16, :16] == COLORS[cell_color_idx[0, 0]])


def test_result_is_identical_for_any_chunk_size(cpu_backend):
  tiles_src, target_src = random_tiles(40), random_target(6, 9)
  params = MosaicParams(cols=9, k=4, alpha=0.6)
  single = run_job(cpu_backend, tiles_src, target_src, params)
  chunked_backend = CpuBackend(chunk_cells=SMALL_CHUNK)
  chunked_backend.warmup()
  chunked = run_job(chunked_backend, tiles_src, target_src, params)
  np.testing.assert_array_equal(single.topk_idx, chunked.topk_idx)
  np.testing.assert_array_equal(single.topk_dist, chunked.topk_dist)
  np.testing.assert_array_equal(single.image, chunked.image)


def test_first_job_after_warmup_does_not_compile():
  backend = CpuBackend()
  backend.warmup()
  before = [list(function.signatures) for function in COMPILED_STAGES]
  run_job(backend, random_tiles(10), random_target(3, 4), MosaicParams(cols=4, k=3, alpha=0.5))
  assert [list(function.signatures) for function in COMPILED_STAGES] == before
  assert backend.init_ms > 0


def test_timings_are_consistent_and_transfers_not_applicable(cpu_backend):
  result = run_job(cpu_backend, random_tiles(20), random_target(4, 5), MosaicParams(cols=5))
  timings = result.timings
  assert timings.total_ms >= timings.stages_sum_ms()
  assert timings.to_dict()["transfer_h2d_ms"] == NOT_APPLICABLE
  assert result.image.shape == (4 * DEFAULT_TILE_PX, 5 * DEFAULT_TILE_PX, RGB_CHANNELS)
  assert result.topk_idx.dtype == np.int32 and result.topk_idx.shape == (4 * 5, DEFAULT_K)


def test_matching_progress_is_reported_per_block(cpu_backend):
  backend = CpuBackend(chunk_cells=SMALL_CHUNK)
  backend.warmup()
  events = []
  run_job(backend, random_tiles(10), random_target(8, 20), MosaicParams(cols=20), lambda s, f: events.append((s, f)))
  matching = [fraction for stage, fraction in events if stage == Stage.MATCHING.value]
  n_blocks = 8 * 20 // SMALL_CHUNK
  assert len(matching) >= n_blocks and matching == sorted(matching)


def test_chunk_size_respects_memory_budget():
  n_tiles = 5000
  chunk = chunk_cells_for_budget(n_tiles, CPU_DISTANCE_BUDGET_BYTES)
  assert chunk * n_tiles * FLOAT32_BYTES <= CPU_DISTANCE_BUDGET_BYTES


def test_numba_vectorization_is_disabled():
  assert numba.config.LOOP_VECTORIZE == 0
  assert numba.config.SLP_VECTORIZE == 0


@pytest.mark.parametrize("function", COMPILED_STAGES)
def test_stages_are_compiled_without_parallel(function):
  assert not function.targetoptions.get("parallel", False)


def test_medium_job_runs_in_a_single_thread(cpu_backend):
  threads_seen = []
  record = lambda stage, fraction: threads_seen.append(threading.active_count())  # noqa: E731
  threads_before = threading.active_count()
  params = MosaicParams(cols=MEDIUM_COLS)
  run_job(cpu_backend, random_tiles(MEDIUM_TILES), random_target(MEDIUM_ROWS, MEDIUM_COLS), params, record)
  assert set(threads_seen) == {threads_before}
  assert threading.active_count() == threads_before
