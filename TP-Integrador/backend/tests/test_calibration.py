import time

from app.backends.cpu.calibration import CpuCalibration, calibrate_cpu, estimate_cpu_seconds

# Cota holgada: con el backend ya compilado la calibración tarda décimas de segundo.
CALIBRATION_MAX_SECONDS = 5.0
CALIBRATION = CpuCalibration(matching_ns_per_pair=50.0, prepare_ns_per_pixel=20.0, compose_ns_per_pixel=10.0)


def test_calibration_is_positive_and_bounded_in_time(cpu_backend):
  start = time.perf_counter()
  calibration = calibrate_cpu(cpu_backend)
  assert time.perf_counter() - start < CALIBRATION_MAX_SECONDS
  assert calibration.matching_ns_per_pair > 0
  assert calibration.prepare_ns_per_pixel > 0
  assert calibration.compose_ns_per_pixel > 0


def test_estimate_grows_with_m_times_n():
  small = estimate_cpu_seconds(CALIBRATION, n_tiles=100, m_cells=1_000, tile_px=32)
  more_cells = estimate_cpu_seconds(CALIBRATION, n_tiles=100, m_cells=10_000, tile_px=32)
  more_tiles = estimate_cpu_seconds(CALIBRATION, n_tiles=1_000, m_cells=10_000, tile_px=32)
  assert small < more_cells < more_tiles


def test_estimate_matches_formula():
  seconds = estimate_cpu_seconds(CALIBRATION, n_tiles=10, m_cells=20, tile_px=16)
  expected_ns = 20 * 10 * 50.0 + 10 * 256 * 20.0 + 20 * 256 * 10.0
  assert seconds == expected_ns / 1e9
