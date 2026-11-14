"""Benchmark sin interfaz de los backends de fotomosaico (cambio 5).

Uso, desde ``TP-Integrador/backend/``::

  python benchmark.py [--backends cuda,opencl,cpu] [--n 100,1000,5000] [--m 1000,10000,40000]
                      [--tile-px 32] [--k 5] [--alpha 1.0] [--repeats 3] [--seed 0]
                      [--max-cpu-seconds 600] [--out-dir resultados]

Detecta y precalienta solo los backends pedidos (CUDA y OpenCL se miden por
separado, aunque estén sobre la misma placa), calibra la CPU para estimar cada
combinación, mide la grilla N × M con datos sintéticos (``app/bench``) y deja
en ``--out-dir`` la tabla Markdown, el CSV y el gráfico PNG.
"""

import argparse
import logging
import platform
import sys
from pathlib import Path

from app.backends.cpu.calibration import calibrate_cpu, estimate_cpu_seconds
from app.backends.registry import CPU, DEFAULT_FACTORIES, LOG_FORMAT, BackendRegistry, BackendStatus
from app.bench.defaults import (
  BENCH_ALPHA,
  BENCH_K,
  BENCH_SEED,
  BENCH_TILE_PX,
  CSV_NAME,
  DEFAULT_BACKENDS,
  DEFAULT_M_VALUES,
  DEFAULT_MAX_CPU_SECONDS,
  DEFAULT_N_VALUES,
  DEFAULT_OUT_DIR,
  DEFAULT_REPEATS,
  MARKDOWN_NAME,
  PLOT_NAME,
)
from app.bench.measure import Benchmark, BenchmarkConfig, ComboResult, CpuEstimator
from app.bench.report import grouped, render_report, write_csv, write_plot
from app.bench.synthetic import grid_shape
from app.core.backend import MosaicBackend
from app.core.params import MosaicParams

LIST_SEPARATOR = ","
EXIT_OK = 0
EXIT_NO_BACKENDS = 1
MIN_REPEATS = 1
OUTPUT_ENCODING = "utf-8"


def _int_list(text: str) -> tuple[int, ...]:
  """Lista de enteros positivos separados por comas ("100,1000")."""
  try:
    values = tuple(int(part) for part in text.split(LIST_SEPARATOR))
  except ValueError as error:
    raise argparse.ArgumentTypeError(f"se esperaba una lista de enteros separados por comas: {text!r}") from error
  if any(value < 1 for value in values):
    raise argparse.ArgumentTypeError(f"los tamaños tienen que ser positivos: {text!r}")
  return values


def _backend_list(text: str) -> tuple[str, ...]:
  """Lista de backends conocidos separados por comas ("cuda,cpu")."""
  names = tuple(part.strip() for part in text.split(LIST_SEPARATOR))
  unknown = [name for name in names if name not in DEFAULT_FACTORIES]
  if unknown:
    raise argparse.ArgumentTypeError(
      f"backends desconocidos: {', '.join(unknown)} (válidos: {', '.join(DEFAULT_FACTORIES)})"
    )
  return names


def _join(values: tuple) -> str:
  """Valor por defecto de una lista, tal como se escribe en la línea de comandos."""
  return LIST_SEPARATOR.join(str(value) for value in values)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
  """Opciones de design D1; los valores por defecto viven en ``app/bench/defaults.py``."""
  parser = argparse.ArgumentParser(description="Benchmark de los backends de fotomosaico sobre una grilla N × M.")
  parser.add_argument(
    "--backends", type=_backend_list, default=DEFAULT_BACKENDS, help=f"(por defecto {_join(DEFAULT_BACKENDS)})"
  )
  parser.add_argument(
    "--n",
    type=_int_list,
    default=DEFAULT_N_VALUES,
    help=f"cantidades de teselas (por defecto {_join(DEFAULT_N_VALUES)})",
  )
  parser.add_argument(
    "--m",
    type=_int_list,
    default=DEFAULT_M_VALUES,
    help=f"cantidades de celdas (por defecto {_join(DEFAULT_M_VALUES)})",
  )
  parser.add_argument(
    "--tile-px", type=int, default=BENCH_TILE_PX, help=f"lado de la tesela en la salida (por defecto {BENCH_TILE_PX})"
  )
  parser.add_argument("--k", type=int, default=BENCH_K, help=f"candidatos por celda (por defecto {BENCH_K})")
  parser.add_argument(
    "--alpha", type=float, default=BENCH_ALPHA, help=f"mezcla con el objetivo (por defecto {BENCH_ALPHA})"
  )
  parser.add_argument(
    "--repeats", type=int, default=DEFAULT_REPEATS, help=f"repeticiones por medición (por defecto {DEFAULT_REPEATS})"
  )
  parser.add_argument(
    "--seed", type=int, default=BENCH_SEED, help=f"semilla de los datos y de choice (por defecto {BENCH_SEED})"
  )
  parser.add_argument(
    "--max-cpu-seconds", type=float, default=DEFAULT_MAX_CPU_SECONDS, help="omite en CPU lo que se estime más largo"
  )
  parser.add_argument(
    "--out-dir", type=Path, default=Path(DEFAULT_OUT_DIR), help=f"directorio de salida (por defecto {DEFAULT_OUT_DIR})"
  )
  args = parser.parse_args(argv)
  _validate(parser, args)
  return args


def _validate(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
  """Falla antes de medir si los parámetros del trabajo son inválidos (``k`` se recorta a N después)."""
  try:
    MosaicParams(cols=grid_shape(args.m[0])[1], tile_px=args.tile_px, k=args.k, alpha=args.alpha, seed=args.seed)
  except ValueError as error:
    parser.error(str(error))
  if args.repeats < MIN_REPEATS:
    parser.error(f"--repeats tiene que ser al menos {MIN_REPEATS}")


def _config(args: argparse.Namespace) -> BenchmarkConfig:
  """Configuración del bucle de medición a partir de las opciones."""
  return BenchmarkConfig(
    args.n, args.m, args.tile_px, args.k, args.alpha, args.seed, args.repeats, args.max_cpu_seconds
  )


def _report_statuses(statuses: list[BackendStatus]) -> None:
  """Estado de cada backend pedido y su tiempo de inicialización (warmup)."""
  print("Backends:")
  for status in statuses:
    init = f", inicialización {status.init_ms:.1f} ms" if status.available else ""
    print(f"  {status.describe()}{init}")


def _cpu_estimator(registry: BackendRegistry, backends: list[MosaicBackend], tile_px: int) -> CpuEstimator | None:
  """Calibra la CPU (si se mide) y devuelve la estimación en segundos para (N, M)."""
  if not any(backend.name == CPU for backend in backends):
    return None
  calibration = calibrate_cpu(registry.resolve([CPU])[0])
  print(f"Calibración de CPU: {calibration.matching_ns_per_pair:.2f} ns por par celda-tesela")
  return lambda n_tiles, m_cells: estimate_cpu_seconds(calibration, n_tiles, m_cells, tile_px)


def _report_estimate(config: BenchmarkConfig, estimator: CpuEstimator | None) -> None:
  """Duración estimada de la parte de CPU antes de empezar a medir."""
  if estimator is None:
    print("Estimación: CPU no se mide.")
    return
  estimates = [estimator(n_tiles, m_cells) for n_tiles, m_cells in config.combinations()]
  kept = [seconds for seconds in estimates if seconds <= config.max_cpu_seconds]
  skipped = len(estimates) - len(kept)
  total = sum(kept) * config.repeats
  print(f"Estimación de CPU: {total:.1f} s (repeticiones: {config.repeats}; {skipped} combinaciones omitidas)")


def _context_lines(statuses: list[BackendStatus], config: BenchmarkConfig) -> list[str]:
  """Hardware y parámetros, para que el reporte se pueda interpretar solo."""
  lines = [status.describe() for status in statuses]
  lines.append(f"{platform.system()} {platform.release()}, Python {platform.python_version()}")
  lines.append(f"tile_px = {config.tile_px}, k = {config.k}, alpha = {config.alpha}, seed = {config.seed}")
  lines.append(
    f"repeticiones por medición: {config.repeats}; CPU omitida si se estima en más de {config.max_cpu_seconds:.0f} s"
  )
  shapes = {m_cells: grid_shape(m_cells) for m_cells in config.m_values}
  grids = ", ".join(f"M = {grouped(m_cells)} → {rows} × {cols}" for m_cells, (rows, cols) in shapes.items())
  lines.append(f"grillas (filas × columnas): {grids}")
  return lines


def _write_outputs(combos: list[ComboResult], names: list[str], out_dir: Path, report: str) -> None:
  """Escribe el Markdown, el CSV y el PNG en ``out_dir``."""
  out_dir.mkdir(parents=True, exist_ok=True)
  (out_dir / MARKDOWN_NAME).write_text(report, encoding="utf-8")
  write_csv(combos, out_dir / CSV_NAME)
  write_plot(combos, names, out_dir / PLOT_NAME)
  print(f"Salidas: {out_dir / MARKDOWN_NAME}, {out_dir / CSV_NAME}, {out_dir / PLOT_NAME}")


def main(argv: list[str] | None = None) -> int:
  """Detecta, calibra, mide e informa; devuelve el código de salida."""
  args = parse_args(argv)
  # La consola de Windows usa cp1252 por defecto: el reporte tiene "×", "→" y "—".
  sys.stdout.reconfigure(encoding=OUTPUT_ENCODING)
  logging.basicConfig(level=logging.WARNING, format=LOG_FORMAT)
  config = _config(args)
  with BackendRegistry({name: DEFAULT_FACTORIES[name] for name in args.backends}) as registry:
    statuses = registry.detect_and_warmup()
    _report_statuses(statuses)
    backends = registry.resolve([status.name for status in statuses if status.available])
    if not backends:
      print("No hay ningún backend disponible para medir.")
      return EXIT_NO_BACKENDS
    estimator = _cpu_estimator(registry, backends, config.tile_px)
    _report_estimate(config, estimator)
    combos = Benchmark(backends, config, estimator).run()
  names = [backend.name for backend in backends]
  report = render_report(combos, names, _context_lines(statuses, config))
  print(f"\n{report}")
  _write_outputs(combos, names, args.out_dir, report)
  return EXIT_OK


if __name__ == "__main__":
  sys.exit(main())
