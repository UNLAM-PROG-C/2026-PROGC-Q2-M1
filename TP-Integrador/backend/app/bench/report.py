"""Reporte del benchmark (design D4 del cambio 5): tablas Markdown, CSV y gráfico.

- Tabla de totales: una fila por (N, M), una columna por backend con la mediana
  del total y el mínimo entre paréntesis, más el speedup de cada GPU contra CPU.
- Tabla por etapa: mediana (mínimo) de cada etapa, por backend y tamaño.
- CSV: una fila por repetición, con todas las columnas de ``StageTimings``; las
  combinaciones omitidas o fallidas también tienen su fila.
- Gráfico log-log del total en función de M·N, con marcadores huecos en la
  posición estimada de las combinaciones de CPU omitidas.
- Punto de cruce: el menor M·N a partir del cual la GPU es más rápida que la
  CPU en todos los tamaños medidos más grandes.
"""

import csv
import dataclasses
import statistics
from pathlib import Path

from app.backends.registry import CPU, DISPLAY_NAMES
from app.bench.defaults import PLOT_DPI, PLOT_GRID_ALPHA, PLOT_SIZE_INCHES
from app.bench.measure import BackendOutcome, ComboResult
from app.core.result import COMPARED_STAGES, OPTIONAL_STAGES, StageTimings
from app.core.timing import MS_PER_SECOND

NOT_MEASURED = "—"
THOUSANDS_SEPARATOR = "."
STATUS_MEASURED = "medido"
STATUS_SKIPPED = "omitido"
STATUS_FAILED = "falló"
ALL_IDENTICAL = "verificación: resultados idénticos en todas las combinaciones"
NOTHING_VERIFIED = "verificación: no aplica (se midió un solo backend en cada combinación)"
TIMING_FIELDS = tuple(field.name for field in dataclasses.fields(StageTimings))
CSV_HEADER = (
  "backend",
  "device",
  "n_tiles",
  "m_cells",
  "mn",
  "rows",
  "cols",
  "repetition",
  "status",
  "estimated_cpu_s",
  "failure",
  *TIMING_FIELDS,
)


def grouped(value: int) -> str:
  """Entero con separador de miles rioplatense ("40.000")."""
  return f"{value:,}".replace(",", THOUSANDS_SEPARATOR)


def size_label(combo: ComboResult) -> str:
  """Tamaño de una combinación: "N = 1.000, M = 40.000"."""
  return f"N = {grouped(combo.n_tiles)}, M = {grouped(combo.m_cells)}"


def display_name(backend: str) -> str:
  """Nombre para mostrar de un backend."""
  return DISPLAY_NAMES.get(backend, backend)


def speedup(cpu_ms: float, gpu_ms: float) -> float:
  """Cuántas veces más rápido es ``gpu_ms`` que ``cpu_ms``."""
  return cpu_ms / gpu_ms


def _both_measured(combo: ComboResult, gpu: str) -> bool:
  """CPU y ``gpu`` se ejecutaron completos en la combinación."""
  outcomes = combo.outcomes
  return CPU in outcomes and gpu in outcomes and outcomes[CPU].measured and outcomes[gpu].measured


def _gpu_faster(combo: ComboResult, gpu: str) -> bool:
  """La mediana del total de ``gpu`` es menor que la de CPU."""
  return combo.outcomes[gpu].median_total_ms() < combo.outcomes[CPU].median_total_ms()


def crossover(combos: list[ComboResult], gpu: str) -> ComboResult | None:
  """Menor combinación medida a partir de la cual ``gpu`` le gana a CPU en todas las más grandes."""
  compared = sorted((combo for combo in combos if _both_measured(combo, gpu)), key=lambda combo: combo.pairs)
  first = None
  for combo in reversed(compared):
    if not _gpu_faster(combo, gpu):
      break
    first = combo
  return first


def describe_crossover(combos: list[ComboResult], gpu: str) -> str:
  """Frase del punto de cruce de ``gpu`` contra CPU."""
  compared = [combo for combo in combos if _both_measured(combo, gpu)]
  name = display_name(gpu)
  if not compared:
    return f"{name}: sin tamaños medidos también en CPU, no hay punto de cruce"
  if all(_gpu_faster(combo, gpu) for combo in compared):
    return f"{name}: la GPU fue más rápida en todos los tamaños medidos"
  first = crossover(combos, gpu)
  if first is None:
    return f"{name}: no superó a la CPU en el tamaño medido más grande"
  return f"{name}: supera a la CPU a partir de M·N = {grouped(first.pairs)} ({size_label(first)})"


# --- Tablas Markdown ------------------------------------------------------------------


def _total_cell(outcome: BackendOutcome | None) -> str:
  """Celda de la tabla de totales: "mediana (mín)", omitido o falló."""
  if outcome is None:
    return NOT_MEASURED
  if outcome.skipped:
    return f"{STATUS_SKIPPED} (estimado {outcome.estimated_seconds:.0f} s)"
  if outcome.failure is not None:
    return f"{STATUS_FAILED} ({outcome.failure})"
  return f"{outcome.median_total_ms():.1f} ({outcome.min_total_ms():.1f})"


def _speedup_cell(combo: ComboResult, gpu: str) -> str:
  """Speedup de la mediana del total, o "—" si falta alguno de los dos."""
  if not _both_measured(combo, gpu):
    return NOT_MEASURED
  return f"{speedup(combo.outcomes[CPU].median_total_ms(), combo.outcomes[gpu].median_total_ms()):.2f}×"


def _markdown(header: list[str], rows: list[list[str]]) -> str:
  """Tabla Markdown con encabezado."""
  lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
  lines.extend("| " + " | ".join(row) + " |" for row in rows)
  return "\n".join(lines)


def gpu_backends(backends: list[str]) -> list[str]:
  """Backends GPU entre los medidos (todos menos CPU)."""
  return [name for name in backends if name != CPU]


def totals_table(combos: list[ComboResult], backends: list[str]) -> str:
  """Tabla de totales en ms con mediana (mínimo) y speedup contra CPU."""
  speedups = gpu_backends(backends) if CPU in backends else []
  header = ["N", "M", "M·N", *(f"{display_name(name)} [ms]" for name in backends)]
  header += [f"Speedup {display_name(name)}" for name in speedups]
  rows = []
  for combo in combos:
    row = [grouped(combo.n_tiles), grouped(combo.m_cells), grouped(combo.pairs)]
    row += [_total_cell(combo.outcomes.get(name)) for name in backends]
    rows.append(row + [_speedup_cell(combo, name) for name in speedups])
  return _markdown(header, rows)


def _stage_cell(timings: list[StageTimings], stage_field: str) -> str:
  """Mediana (mínimo) de una etapa, o "no aplica" si el backend no la tiene."""
  values = [getattr(timing, stage_field) for timing in timings if getattr(timing, stage_field) is not None]
  if not values:
    return "no aplica"
  return f"{statistics.median(values):.1f} ({min(values):.1f})"


def stages_table(combos: list[ComboResult], backends: list[str]) -> str:
  """Mediana (mínimo) en ms de cada etapa, por backend medido y tamaño."""
  stage_fields = [f"{stage.value}_ms" for stage in (*COMPARED_STAGES, *OPTIONAL_STAGES)]
  header = ["Backend", "N", "M", *(field.removesuffix("_ms") for field in stage_fields), "total"]
  rows = []
  for combo in combos:
    for name in backends:
      outcome = combo.outcomes.get(name)
      if outcome is not None and outcome.measured:
        cells = [_stage_cell(outcome.timings, field) for field in (*stage_fields, "total_ms")]
        rows.append([display_name(name), grouped(combo.n_tiles), grouped(combo.m_cells), *cells])
  return _markdown(header, rows)


# --- Verificación -----------------------------------------------------------------------


def verification_lines(combos: list[ComboResult]) -> list[str]:
  """Resumen de la verificación: todo idéntico, o qué combinaciones difieren."""
  verified = [combo for combo in combos if combo.verification is not None]
  if not verified:
    return [NOTHING_VERIFIED]
  differing = [combo for combo in verified if not combo.verification.identical]
  if not differing:
    return [ALL_IDENTICAL]
  return [line for combo in differing for line in _difference_lines(combo)]


def _difference_lines(combo: ComboResult) -> list[str]:
  """Una línea por backend que difiere de la referencia en esta combinación."""
  summary = combo.verification
  reference = display_name(summary.reference)
  return [
    f"verificación: {size_label(combo)}: {display_name(name)} difiere de {reference} en "
    f"{diff.total_cells} celdas (top-k: {diff.topk_cells}, imagen: {diff.image_cells})"
    for name, diff in summary.differences.items()
    if diff.total_cells
  ]


# --- CSV --------------------------------------------------------------------------------


def _csv_value(value: float | int | str | None) -> str | float | int:
  """Celda del CSV; lo que no aplica queda vacío (no es lo mismo que cero)."""
  return "" if value is None else value


def _csv_rows(combo: ComboResult, outcome: BackendOutcome) -> list[list]:
  """Filas de un backend en una combinación: una por repetición, o una sola si no se midió."""
  base = [outcome.name, outcome.device_name, combo.n_tiles, combo.m_cells, combo.pairs, combo.rows, combo.cols]
  extra = [_csv_value(outcome.estimated_seconds), _csv_value(outcome.failure)]
  if not outcome.measured:
    status = STATUS_SKIPPED if outcome.skipped else STATUS_FAILED
    return [[*base, "", status, *extra, *("" for _ in TIMING_FIELDS)]]
  return [
    [*base, repetition, STATUS_MEASURED, *extra, *(_csv_value(getattr(timing, name)) for name in TIMING_FIELDS)]
    for repetition, timing in enumerate(outcome.timings, start=1)
  ]


def write_csv(combos: list[ComboResult], path: Path) -> None:
  """Escribe todas las mediciones, una fila por repetición."""
  with path.open("w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(CSV_HEADER)
    for combo in combos:
      for outcome in combo.outcomes.values():
        writer.writerows(_csv_rows(combo, outcome))


# --- Gráfico ----------------------------------------------------------------------------


def _series(combos: list[ComboResult], backend: str) -> tuple[list, list, list, list]:
  """Puntos medidos (M·N, segundos) y puntos omitidos en su posición estimada."""
  measured_x, measured_y, skipped_x, skipped_y = [], [], [], []
  for combo in sorted(combos, key=lambda combo: (combo.pairs, combo.n_tiles)):
    outcome = combo.outcomes.get(backend)
    if outcome is not None and outcome.measured:
      measured_x.append(combo.pairs)
      measured_y.append(outcome.median_total_ms() / MS_PER_SECOND)
    elif outcome is not None and outcome.skipped:
      skipped_x.append(combo.pairs)
      skipped_y.append(outcome.estimated_seconds)
  return measured_x, measured_y, skipped_x, skipped_y


def _plot_backend(axes, combos: list[ComboResult], backend: str) -> None:
  """Línea del backend y, si hay, marcadores huecos de lo omitido."""
  measured_x, measured_y, skipped_x, skipped_y = _series(combos, backend)
  (line,) = axes.plot(measured_x, measured_y, marker="o", label=display_name(backend))
  if skipped_x:
    label = f"{display_name(backend)} (omitido, estimado)"
    axes.plot(
      skipped_x, skipped_y, linestyle="none", marker="o", markerfacecolor="none", color=line.get_color(), label=label
    )


def write_plot(combos: list[ComboResult], backends: list[str], path: Path) -> None:
  """Gráfico log-log del tiempo total (mediana) en función de M·N."""
  import matplotlib  # Import diferido: el resto del benchmark no lo necesita.

  matplotlib.use("Agg")
  from matplotlib import pyplot

  figure, axes = pyplot.subplots(figsize=PLOT_SIZE_INCHES)
  for backend in backends:
    _plot_backend(axes, combos, backend)
  axes.set(xscale="log", yscale="log", xlabel="M·N (pares celda-tesela)", ylabel="tiempo total, mediana (s)")
  axes.set_title("Fotomosaico: tiempo total por backend")
  axes.grid(True, which="both", alpha=PLOT_GRID_ALPHA)
  axes.legend()
  figure.tight_layout()
  figure.savefig(path, dpi=PLOT_DPI)
  pyplot.close(figure)


# --- Reporte completo ----------------------------------------------------------------------


def _bullets(lines: list[str]) -> str:
  """Lista Markdown."""
  return "\n".join(f"- {line}" for line in lines)


def render_report(combos: list[ComboResult], backends: list[str], context_lines: list[str]) -> str:
  """Reporte Markdown: contexto (hardware y parámetros), tablas, cruce y verificación."""
  sections = ["## Contexto", _bullets(context_lines)]
  sections += ["## Tiempo total [ms]: mediana (mínimo)", totals_table(combos, backends)]
  if CPU in backends and gpu_backends(backends):
    sections += ["## Punto de cruce", _bullets([describe_crossover(combos, gpu) for gpu in gpu_backends(backends)])]
  sections += ["## Verificación", _bullets(verification_lines(combos))]
  sections += ["## Detalle por etapa [ms]: mediana (mínimo)", stages_table(combos, backends)]
  return "\n\n".join(sections) + "\n"
