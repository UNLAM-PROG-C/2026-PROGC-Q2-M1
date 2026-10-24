import csv

import numpy as np

from app.bench.measure import BackendOutcome, ComboResult
from app.bench.report import (
  ALL_IDENTICAL,
  crossover,
  describe_crossover,
  render_report,
  speedup,
  stages_table,
  totals_table,
  verification_lines,
  write_csv,
  write_plot,
)
from app.core.result import StageTimings
from app.core.verification import fingerprint, verify

BACKENDS = ["cuda", "cpu"]


def timings(total_ms: float, gpu: bool = False) -> StageTimings:
  transfer = 0.5 if gpu else None
  return StageTimings(1.0, 2.0, 3.0, 4.0, total_ms, transfer, transfer, transfer, transfer)


def outcome(name: str, totals: list[float]) -> BackendOutcome:
  return BackendOutcome(name, f"device {name}", [timings(total, gpu=name != "cpu") for total in totals])


def combo(n_tiles: int, m_cells: int, cpu_ms: float | None, cuda_ms: float) -> ComboResult:
  result = ComboResult(n_tiles, m_cells, 1, m_cells)
  result.outcomes["cuda"] = outcome("cuda", [cuda_ms, cuda_ms + 10.0, cuda_ms - 1.0])
  if cpu_ms is None:
    result.outcomes["cpu"] = BackendOutcome("cpu", "device cpu", estimated_seconds=900.0, skipped=True)
  else:
    result.outcomes["cpu"] = outcome("cpu", [cpu_ms, cpu_ms + 5.0, cpu_ms - 1.0])
  return result


def crossing_combos() -> list[ComboResult]:
  # La GPU pierde en el tamaño chico y gana en los grandes; el más grande de CPU se omite.
  return [combo(100, 1_000, 10.0, 20.0), combo(1_000, 10_000, 30_000.0, 150.0), combo(5_000, 40_000, None, 900.0)]


def test_speedup_is_cpu_over_gpu():
  assert speedup(30_000.0, 150.0) == 200.0


def test_totals_table_shows_median_min_speedup_and_skipped():
  table = totals_table(crossing_combos(), BACKENDS)
  assert "| 1.000 | 10.000 | 10.000.000 | 150.0 (149.0) | 30000.0 (29999.0) | 200.00× |" in table
  assert "omitido (estimado 900 s)" in table
  assert "0.50×" in table


def test_crossover_is_detected():
  combos = crossing_combos()
  assert crossover(combos, "cuda") is combos[1]
  assert "a partir de M·N = 10.000.000 (N = 1.000, M = 10.000)" in describe_crossover(combos, "cuda")


def test_gpu_faster_in_every_size():
  combos = [combo(100, 1_000, 30.0, 20.0), combo(1_000, 10_000, 30_000.0, 150.0)]
  assert crossover(combos, "cuda") is combos[0]
  assert describe_crossover(combos, "cuda") == "CUDA: la GPU fue más rápida en todos los tamaños medidos"


def test_gpu_never_faster_at_the_largest_size():
  combos = [combo(100, 1_000, 10.0, 5.0), combo(1_000, 10_000, 100.0, 150.0)]
  assert crossover(combos, "cuda") is None
  assert "no superó" in describe_crossover(combos, "cuda")


def test_stages_table_reports_each_stage_and_not_applicable():
  table = stages_table(crossing_combos(), BACKENDS)
  assert "matching" in table and "transfer_h2d" in table
  assert "| CPU secuencial | 100 | 1.000 | 1.0 (1.0) | 2.0 (2.0) | 3.0 (3.0) | 4.0 (4.0) | no aplica |" in table


def verified_combo(differs: bool) -> ComboResult:
  image = np.zeros((4, 8, 3), dtype=np.uint8)
  topk = np.zeros((2, 3), dtype=np.int32)
  other = topk + 1 if differs else topk
  result = combo(100, 1_000, 10.0, 5.0)
  result.verification = verify({"cpu": fingerprint(image, topk, 4), "cuda": fingerprint(image, other, 4)}, "cpu")
  return result


def test_verification_identical_everywhere():
  assert verification_lines([verified_combo(False), verified_combo(False)]) == [ALL_IDENTICAL]


def test_verification_reports_differing_cells():
  (line,) = verification_lines([verified_combo(False), verified_combo(True)])
  assert "N = 100, M = 1.000: CUDA difiere de CPU secuencial en 2 celdas (top-k: 2, imagen: 0)" in line


def test_csv_has_one_row_per_repetition_and_skipped_rows(tmp_path):
  path = tmp_path / "bench.csv"
  write_csv(crossing_combos(), path)
  rows = list(csv.DictReader(path.open(encoding="utf-8")))
  assert len(rows) == 3 * 3 + 2 * 3 + 1
  skipped = [row for row in rows if row["status"] == "omitido"]
  assert len(skipped) == 1 and skipped[0]["estimated_cpu_s"] == "900.0" and skipped[0]["total_ms"] == ""
  cpu_row = next(row for row in rows if row["backend"] == "cpu")
  assert cpu_row["transfer_h2d_ms"] == "" and cpu_row["mn"] == "100000"


def test_plot_is_written_with_skipped_points(tmp_path):
  path = tmp_path / "bench.png"
  write_plot(crossing_combos(), BACKENDS, path)
  assert path.read_bytes().startswith(b"\x89PNG")


def test_report_has_all_sections():
  report = render_report(crossing_combos(), BACKENDS, ["hardware de prueba"])
  for heading in ("## Contexto", "## Tiempo total", "## Punto de cruce", "## Verificación", "## Detalle por etapa"):
    assert heading in report
