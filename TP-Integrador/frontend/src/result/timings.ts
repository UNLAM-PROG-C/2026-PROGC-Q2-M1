// Filas de la tabla de tiempos (spec "Estadísticas a pedido"). Lo que no
// aplica al backend (por ejemplo las transferencias en CPU) dice "no aplica".

import type {BackendResult, LoadInfo} from '../api/types';
import {formatMs} from '../common/format';

export const NOT_APPLICABLE = 'no aplica';

export interface TimingRow
{
  label: string;
  value: string;
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
