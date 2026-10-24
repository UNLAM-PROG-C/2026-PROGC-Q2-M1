import csv

import pytest

import benchmark
from app.bench.defaults import CSV_NAME, DEFAULT_M_VALUES, DEFAULT_N_VALUES, MARKDOWN_NAME, PLOT_NAME


def test_defaults_measure_the_nine_combinations():
  args = benchmark.parse_args([])
  assert len(args.n) * len(args.m) == 9
  assert (args.n, args.m) == (DEFAULT_N_VALUES, DEFAULT_M_VALUES)


def test_lists_and_subset_of_backends_are_parsed():
  args = benchmark.parse_args(["--backends", "cuda,cpu", "--n", "100,1000", "--m", "1000"])
  assert args.backends == ("cuda", "cpu")
  assert args.n == (100, 1000) and args.m == (1000,)


@pytest.mark.parametrize(
  "argv",
  [["--backends", "metal"], ["--n", "cien"], ["--n", "0"], ["--k", "0"], ["--tile-px", "20"], ["--repeats", "0"]],
)
def test_invalid_options_are_rejected(argv):
  with pytest.raises(SystemExit):
    benchmark.parse_args(argv)


def test_cpu_only_run_writes_table_csv_and_plot(tmp_path, capsys):
  argv = ["--backends", "cpu", "--n", "10", "--m", "12", "--repeats", "2", "--out-dir", str(tmp_path)]
  assert benchmark.main(argv) == benchmark.EXIT_OK
  output = capsys.readouterr().out
  assert "CPU secuencial: siempre disponible" in output and "CUDA" not in output
  assert "| CPU secuencial [ms] |" in output
  rows = list(csv.DictReader((tmp_path / CSV_NAME).open(encoding="utf-8")))
  assert [row["repetition"] for row in rows] == ["1", "2"]
  assert (tmp_path / PLOT_NAME).exists() and (tmp_path / MARKDOWN_NAME).exists()
