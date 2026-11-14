// Formato de números para la interfaz, con las convenciones de es-AR
// (punto de miles y coma decimal: "7.500", "7,5 millones").

const LOCALE = 'es-AR';
const MILLION = 1_000_000;
const SECONDS_PER_MINUTE = 60;
const MS_DECIMALS = 1;
const MILLIONS_DECIMALS = 1;
const MB_DECIMALS = 1;
const BYTES_PER_MB = 1024 * 1024;
export const PERCENT = 100;

const integerFormat = new Intl.NumberFormat(LOCALE, {maximumFractionDigits: 0});
const millionsFormat = new Intl.NumberFormat(LOCALE, {maximumFractionDigits: MILLIONS_DECIMALS});
const msFormat = new Intl.NumberFormat(LOCALE, {minimumFractionDigits: MS_DECIMALS, maximumFractionDigits: MS_DECIMALS});
const mbFormat = new Intl.NumberFormat(LOCALE, {maximumFractionDigits: MB_DECIMALS});

export function formatInt(value: number): string
{
  return integerFormat.format(value);
}

/** Cantidades grandes: "7.500" por debajo del millón, "7,5 millones" desde el millón. */
export function formatCount(value: number): string
{
  if (value < MILLION)
  {
    return formatInt(value);
  }
  const millions = millionsFormat.format(value / MILLION);
  return value === MILLION ? '1 millón' : `${millions} millones`;
}

export function formatMs(value: number): string
{
  return `${msFormat.format(value)} ms`;
}

export function formatMegabytes(bytes: number): string
{
  return `${mbFormat.format(bytes / BYTES_PER_MB)} MB`;
}

/** Duración estimada: "~40 s" o "~3 min". */
export function formatEstimate(seconds: number): string
{
  if (seconds < SECONDS_PER_MINUTE)
  {
    return `~${formatInt(Math.max(1, Math.round(seconds)))} s`;
  }
  return `~${formatInt(Math.round(seconds / SECONDS_PER_MINUTE))} min`;
}

export function formatPercent(fraction: number): string
{
  return `${formatInt(fraction * PERCENT)} %`;
}
