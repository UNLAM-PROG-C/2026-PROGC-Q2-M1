// Filas de la tabla de tiempos (spec "Estadísticas a pedido"). Lo que no
// aplica al backend (por ejemplo las transferencias en CPU) dice "no aplica".
// En una comparación (cambio 4) cada fila lleva CPU, GPU y el speedup.

import type {BackendResult, LoadInfo, StageTimings} from '../api/types';
import {formatMs} from '../common/format';
import {NO_VALUE, speedupText} from './speedup';

export const NOT_APPLICABLE = 'no aplica';

export interface TimingRow
{
  label: string;
  value: string;
}

/** Fila de `TimingsTable`: un valor por columna. */
export interface TableRow
{
  label: string;
  values: string[];
}

function msOrNotApplicable(value: number | null | undefined): string
{
  return value === null || value === undefined ? NOT_APPLICABLE : formatMs(value);
}

function loadValue(load: LoadInfo | null): string
{
  if (!load)
  {
    return NOT_APPLICABLE;
  }
  return load.reused ? `${formatMs(load.load_ms)} (reutilizada)` : formatMs(load.load_ms);
}

export function timingRows(load: LoadInfo | null, result: BackendResult): TimingRow[]
{
  const timings = result.timings;
  return [
    {label: 'Carga común', value: loadValue(load)},
    {label: 'Preparación de teselas', value: formatMs(timings.prepare_tiles_ms)},
    {label: 'Descriptores del objetivo', value: formatMs(timings.target_descriptors_ms)},
    {label: 'Matching + top-k', value: formatMs(timings.matching_ms)},
    {label: 'Composición', value: formatMs(timings.compose_ms)},
    {label: 'Transferencia host→device: copia a staging', value: msOrNotApplicable(timings.staging_h2d_ms)},
    {label: 'Transferencia host→device: DMA', value: msOrNotApplicable(timings.transfer_h2d_ms)},
    {label: 'Transferencia device→host: DMA', value: msOrNotApplicable(timings.transfer_d2h_ms)},
    {label: 'Transferencia device→host: copia desde staging', value: msOrNotApplicable(timings.staging_d2h_ms)},
    {label: 'Total del backend', value: formatMs(timings.total_ms)},
    {label: 'Inicialización del backend', value: msOrNotApplicable(result.init_ms)},
  ];
}

export function singleTableRows(load: LoadInfo | null, result: BackendResult): TableRow[]
{
  return timingRows(load, result).map((row) => ({label: row.label, values: [row.value]}));
}

/** Etapas en las que se calcula el speedup (las de cómputo y el total). */
const COMPARED_KEYS: Readonly<Record<string, keyof StageTimings>> = {
  'Preparación de teselas': 'prepare_tiles_ms',
  'Descriptores del objetivo': 'target_descriptors_ms',
  'Matching + top-k': 'matching_ms',
  'Composición': 'compose_ms',
  'Total del backend': 'total_ms',
};

/** Filas CPU | GPU | speedup; las que no se comparan (carga, transferencias, inicialización) dicen "—". */
export function comparisonRows(load: LoadInfo | null, cpu: BackendResult, gpu: BackendResult): TableRow[]
{
  const gpuRows = timingRows(load, gpu);
  return timingRows(load, cpu).map((row, index) =>
  {
    const key = COMPARED_KEYS[row.label];
    const ratio = key ? speedupText(cpu.timings[key], gpu.timings[key]) : NO_VALUE;
    return {label: row.label, values: [row.value, gpuRows[index].value, ratio]};
  });
}
