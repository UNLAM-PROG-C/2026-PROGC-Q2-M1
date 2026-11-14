// Speedup de la GPU respecto de la CPU (design D4): `t_cpu / t_gpu` por etapa
// y para el total. Se calcula en el cliente porque los tiempos ya llegan por
// backend; si falta un tiempo o es cero se muestra "—".

import {formatInt} from '../common/format';

export const NO_VALUE = '—';
/** Desde este speedup se muestra sin decimales ("200×"); por debajo, con uno ("3,5×"). */
const INTEGER_SPEEDUP_FROM = 10;
const SPEEDUP_DECIMALS = 1;

const decimalFormat = new Intl.NumberFormat('es-AR', {maximumFractionDigits: SPEEDUP_DECIMALS});

function isPositive(value: number | null | undefined): value is number
{
  return typeof value === 'number' && Number.isFinite(value) && value > 0;
}

/** `cpuMs / gpuMs`, o `null` si alguno falta o no es positivo. */
export function speedup(cpuMs: number | null | undefined, gpuMs: number | null | undefined): number | null
{
  return isPositive(cpuMs) && isPositive(gpuMs) ? cpuMs / gpuMs : null;
}

export function formatSpeedup(value: number | null): string
{
  if (value === null)
  {
    return NO_VALUE;
  }
  return value >= INTEGER_SPEEDUP_FROM ? `${formatInt(value)}×` : `${decimalFormat.format(value)}×`;
}

/** Atajo: speedup ya formateado a partir de los dos tiempos. */
export function speedupText(cpuMs: number | null | undefined, gpuMs: number | null | undefined): string
{
  return formatSpeedup(speedup(cpuMs, gpuMs));
}
