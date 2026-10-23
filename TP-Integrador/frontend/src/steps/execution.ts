// Lógica del paso 3 sin DOM: textos de las opciones, motivo por el que no se
// puede ejecutar y estimación de CPU con confirmación (design D4 y D8). La
// opción "Ambas" (cambio 4) corre GPU y CPU, así que también se estima.

import type {AppState, ExecutionMode, GpuOption, JobRequest} from '../api/types';
import {isJobRunning} from '../app/serverState';
import type {WizardState} from '../wizard/wizardReducer';
import {draftProblemInfo, estimateCpuSeconds, toJobParams} from './params';

/** Motivo por defecto si el backend no informa por qué no hay GPU. */
export const NO_GPU_REASON = 'no se detectó una GPU compatible';

/** Por ejemplo "GPU — CUDA (GeForce RTX 3060)". */
export function gpuTitle(gpu: GpuOption): string
{
  if (!gpu.available || !gpu.api)
  {
    return 'GPU';
  }
  return gpu.device ? `GPU — ${gpu.api} (${gpu.device})` : `GPU — ${gpu.api}`;
}

export function isModeAvailable(server: AppState, mode: ExecutionMode): boolean
{
  return server.execution[mode].available;
}

/** Motivo por el que "Generar mosaico" está deshabilitado, o `null`. */
export function runBlocker(server: AppState | null, connected: boolean, mode: ExecutionMode): string | null
{
  if (!server || !connected)
  {
    return 'sin conexión con el backend';
  }
  if (isJobRunning(server))
  {
    return 'hay un trabajo en curso';
  }
  if (!server.worker.ready)
  {
    return server.worker.error ?? 'preparando el procesamiento…';
  }
  return isModeAvailable(server, mode) ? null : 'la forma de ejecución elegida no está disponible';
}

/** Segundos estimados en CPU, o `null` si no hay calibración o datos suficientes. */
export function cpuEstimateSeconds(server: AppState | null, wizard: WizardState): number | null
{
  const info = draftProblemInfo(wizard.tiles, wizard.target, wizard.params);
  if (!server?.calibration || !info || !wizard.params)
  {
    return null;
  }
  return estimateCpuSeconds(server.calibration, info, wizard.params.tilePx);
}

/** "CPU" y "Ambas" ejecutan en CPU: a las dos se les aplica la estimación (spec "Estimación de la comparación"). */
export function runsOnCpu(mode: ExecutionMode): boolean
{
  return mode === 'cpu' || mode === 'both';
}

export function needsConfirmation(server: AppState | null, wizard: WizardState): boolean
{
  const seconds = cpuEstimateSeconds(server, wizard);
  return runsOnCpu(wizard.mode) && seconds !== null && server !== null && seconds > server.rules.cpu_confirm_seconds;
}

export function buildJobRequest(wizard: WizardState): JobRequest | null
{
  if (!wizard.tiles || !wizard.target || !wizard.params)
  {
    return null;
  }
  return {tiles_id: wizard.tiles.tiles_id, target_id: wizard.target.target_id, mode: wizard.mode, ...toJobParams(wizard.params)};
}
