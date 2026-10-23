// Datos del gráfico comparativo, sin Chart.js ni DOM (design D5): categorías =
// etapas comparadas, transferencias y total; una serie por backend.

import type {BackendResult, StageTimings} from '../api/types';

/** Si la barra más alta supera a la más baja en más que esta razón, el eje arranca en escala logarítmica. */
export const LOG_SCALE_RATIO = 100;

interface ChartCategory
{
  label: string;
  value: (timings: StageTimings) => number | null;
}

const TRANSFER_KEYS = ['staging_h2d_ms', 'transfer_h2d_ms', 'transfer_d2h_ms', 'staging_d2h_ms'] as const;

/** Suma de las transferencias medidas, o `null` si no aplican (CPU). */
export function transfersMs(timings: StageTimings): number | null
{
  const measured = TRANSFER_KEYS.map((key) => timings[key]).filter((value): value is number => value !== null);
  return measured.length === 0 ? null : measured.reduce((sum, value) => sum + value, 0);
}

export const CHART_CATEGORIES: readonly ChartCategory[] = [
  {label: 'Preparación de teselas', value: (timings) => timings.prepare_tiles_ms},
  {label: 'Descriptores del objetivo', value: (timings) => timings.target_descriptors_ms},
  {label: 'Matching + top-k', value: (timings) => timings.matching_ms},
  {label: 'Composición', value: (timings) => timings.compose_ms},
  {label: 'Transferencias', value: transfersMs},
  {label: 'Total', value: (timings) => timings.total_ms},
];

/** Valores de una serie; los que no aplican quedan en `null` (sin barra). */
export function seriesValues(result: BackendResult): (number | null)[]
{
  return CHART_CATEGORIES.map((category) => category.value(result.timings));
}

/** Escala logarítmica por defecto si la razón entre la barra más alta y la más baja supera `LOG_SCALE_RATIO`. */
export function prefersLogScale(series: (number | null)[][]): boolean
{
  const positive = series.flat().filter((value): value is number => value !== null && value > 0);
  if (positive.length === 0)
  {
    return false;
  }
  return Math.max(...positive) / Math.min(...positive) > LOG_SCALE_RATIO;
}
