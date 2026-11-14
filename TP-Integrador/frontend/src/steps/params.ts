// Lógica del paso 2 sin DOM: borrador de parámetros, validación con las reglas
// que manda el backend, información del problema y estimación de CPU (design D8).

import type {CpuCalibration, JobParams, ParamRules, TargetSummary, TilesSummary} from '../api/types';
import {formatInt, PERCENT} from '../common/format';

/** Valores tal como los edita la persona (los campos de texto pueden ser inválidos). */
export interface ParamDraft
{
  cols: string;
  tilePx: number;
  opacityPercent: number;
  seed: string;
}

export interface ParamErrors
{
  cols?: string;
  seed?: string;
  output?: string;
}

export interface ProblemInfo
{
  n: number;
  rows: number;
  cols: number;
  m: number;
  pairs: number;
  width: number;
  height: number;
  bytes: number;
}

const RGB_BYTES_PER_PIXEL = 3;
const ROUND_HALF = 0.5;
const NS_PER_SECOND = 1e9;
const MEGAPIXEL = 1_000_000;
const INTEGER_PATTERN = /^\d+$/;

/** Columnas por defecto si el backend no las informa. */
export const FALLBACK_DEFAULT_COLS = 100;

export function defaultDraft(rules: ParamRules): ParamDraft
{
  return {
    cols: String(rules.cols.default ?? FALLBACK_DEFAULT_COLS),
    tilePx: rules.tile_px.default,
    opacityPercent: Math.round(rules.alpha.default * PERCENT),
    seed: String(rules.seed.default),
  };
}

/** Lo inverso de `toJobParams`: recupera el borrador de los últimos parámetros usados. */
export function draftFromParams(params: JobParams): ParamDraft
{
  return {cols: String(params.cols), tilePx: params.tile_px, opacityPercent: Math.round(params.alpha * PERCENT), seed: String(params.seed)};
}

/** Entero no negativo escrito en el campo, o `null` si no es válido. */
export function parseInteger(text: string): number | null
{
  const trimmed = text.trim();
  return INTEGER_PATTERN.test(trimmed) ? Number(trimmed) : null;
}

/** La opacidad se muestra de 0 a 100 % y viaja como `alpha` entre 0 y 1. */
export function opacityToAlpha(opacityPercent: number): number
{
  return opacityPercent / PERCENT;
}

export function toJobParams(draft: ParamDraft): JobParams
{
  return {cols: parseInteger(draft.cols) ?? 0, tile_px: draft.tilePx, alpha: opacityToAlpha(draft.opacityPercent), seed: parseInteger(draft.seed) ?? 0};
}

/** Filas de la grilla, con la misma regla que `derive_rows()` del backend. */
export function deriveRows(cols: number, width: number, height: number): number
{
  return Math.max(1, Math.floor(cols * height / width + ROUND_HALF));
}

export function problemInfo(n: number, cols: number, tilePx: number, target: TargetSummary): ProblemInfo
{
  const rows = deriveRows(cols, target.width, target.height);
  const m = rows * cols;
  const width = cols * tilePx;
  const height = rows * tilePx;
  return {n, rows, cols, m, pairs: m * n, width, height, bytes: width * height * RGB_BYTES_PER_PIXEL};
}

/** Información del problema para el borrador actual, o `null` si faltan datos o las columnas no son un entero positivo. */
export function draftProblemInfo(tiles: TilesSummary | null, target: TargetSummary | null, draft: ParamDraft | null): ProblemInfo | null
{
  const cols = draft ? parseInteger(draft.cols) : null;
  if (!tiles || !target || !draft || !cols)
  {
    return null;
  }
  return problemInfo(tiles.accepted, cols, draft.tilePx, target);
}

function rangeError(value: number | null, min: number, max: number): string | undefined
{
  if (value === null || value < min || value > max)
  {
    return `Ingresá un número entero entre ${formatInt(min)} y ${formatInt(max)}.`;
  }
  return undefined;
}

function outputError(cols: number, draft: ParamDraft, rules: ParamRules, target: TargetSummary | null): string | undefined
{
  if (!target)
  {
    return undefined;
  }
  const info = problemInfo(0, cols, draft.tilePx, target);
  if (info.width * info.height <= rules.max_output_pixels)
  {
    return undefined;
  }
  const limit = formatInt(rules.max_output_pixels / MEGAPIXEL);
  return `La imagen final (${formatInt(info.width)} × ${formatInt(info.height)} px) supera el límite de ${limit} megapíxeles. Bajá las columnas o la resolución.`;
}

export function validateParams(draft: ParamDraft, rules: ParamRules, target: TargetSummary | null): ParamErrors
{
  const cols = parseInteger(draft.cols);
  const errors: ParamErrors = {
    cols: rangeError(cols, rules.cols.min, rules.cols.max),
    seed: rangeError(parseInteger(draft.seed), rules.seed.min, rules.seed.max),
  };
  if (!errors.cols && cols !== null)
  {
    errors.output = outputError(cols, draft, rules, target);
  }
  return errors;
}

export function firstError(errors: ParamErrors): string | null
{
  return errors.cols ?? errors.seed ?? errors.output ?? null;
}

/** Segundos estimados en CPU: pares·c_pares + píxeles preparados·c_prep + píxeles compuestos·c_comp. */
export function estimateCpuSeconds(calibration: CpuCalibration, info: ProblemInfo, tilePx: number): number
{
  const tilePixels = tilePx * tilePx;
  const matchingNs = info.pairs * calibration.matching_ns_per_pair;
  const prepareNs = info.n * tilePixels * calibration.prepare_ns_per_pixel;
  const composeNs = info.m * tilePixels * calibration.compose_ns_per_pixel;
  return (matchingNs + prepareNs + composeNs) / NS_PER_SECOND;
}
