// Datos de prueba compartidos por los tests: un estado del backend completo y
// subidas típicas. Los valores replican las constantes del backend.

import type {AppState, BackendResult, JobSnapshot, ParamRules, TargetSummary, TilesSummary} from '../api/types';
import {INITIAL_WIZARD_STATE, type WizardState} from '../wizard/wizardReducer';
import {defaultDraft} from '../steps/params';

const TEST_MAX_COLS = 400;
const TEST_DEFAULT_COLS = 100;
const TEST_MAX_SEED = 2 ** 31 - 1;
const TEST_MAX_OUTPUT_PIXELS = 400_000_000;
const TEST_CPU_CONFIRM_SECONDS = 60;
const TEST_TILE_SIZES = [16, 32, 64];
const TEST_DEFAULT_TILE_PX = 32;
const TEST_TILES = 1000;
const TARGET_WIDTH = 4000;
const TARGET_HEIGHT = 3000;

export function makeRules(overrides: Partial<ParamRules> = {}): ParamRules
{
  return {
    cols: {min: 1, max: TEST_MAX_COLS, default: TEST_DEFAULT_COLS},
    tile_px: {allowed: TEST_TILE_SIZES, default: TEST_DEFAULT_TILE_PX},
    alpha: {min: 0, max: 1, default: 1},
    seed: {min: 0, max: TEST_MAX_SEED, default: 0},
    max_output_pixels: TEST_MAX_OUTPUT_PIXELS,
    cpu_confirm_seconds: TEST_CPU_CONFIRM_SECONDS,
    ...overrides,
  };
}

export function makeTiles(accepted: number = TEST_TILES): TilesSummary
{
  return {tiles_id: 'tiles-1', accepted, ignored: 0, rejected: 0, samples: ['a.jpg', 'b.jpg']};
}

/** Objetivo 4:3 como en el escenario "Cambio de columnas". */
export function makeTarget(): TargetSummary
{
  return {target_id: 'target-1', filename: 'objetivo.jpg', width: TARGET_WIDTH, height: TARGET_HEIGHT};
}

export function makeAppState(overrides: Partial<AppState> = {}): AppState
{
  return {
    worker: {ready: true, error: null},
    backends: [],
    execution: {
      cpu: {available: true, device: 'CPU de prueba'},
      gpu: {available: false, api: null, device: null, reason: 'no se detectó una GPU compatible'},
      both: {available: false, reason: 'no se detectó una GPU compatible'},
    },
    calibration: null,
    rules: makeRules(),
    job: null,
    last_tiles: null,
    last_target: null,
    ...overrides,
  };
}

export function makeJob(overrides: Partial<JobSnapshot> = {}): JobSnapshot
{
  return {
    job_id: 'job-1',
    status: 'running',
    mode: 'cpu',
    backends: ['cpu'],
    tiles_id: 'tiles-1',
    target_id: 'target-1',
    params: {cols: TEST_DEFAULT_COLS, tile_px: TEST_DEFAULT_TILE_PX, alpha: 1, seed: 0, k: 5},
    progress: null,
    load: null,
    results: [],
    failures: [],
    verification: null,
    error: null,
    ...overrides,
  };
}

/** Stepper con reglas cargadas, lote y objetivo subidos, en la fase indicada. */
export function makeWizard(overrides: Partial<WizardState> = {}): WizardState
{
  const rules = makeRules();
  return {...INITIAL_WIZARD_STATE, hydrated: true, rules, params: defaultDraft(rules), tiles: makeTiles(), target: makeTarget(), ...overrides};
}

/** Resultado de CPU: las transferencias no aplican (`null`). */
export function makeCpuResult(): BackendResult
{
  const timings = {prepare_tiles_ms: 1, target_descriptors_ms: 2, matching_ms: 3, compose_ms: 4, total_ms: 10};
  return {
    backend: 'cpu',
    device: 'CPU de prueba',
    timings: {...timings, transfer_h2d_ms: null, transfer_d2h_ms: null, staging_h2d_ms: null, staging_d2h_ms: null},
    init_ms: 5,
    width: TARGET_WIDTH,
    height: TARGET_HEIGHT,
  };
}

/** Resultado de GPU (CUDA) con transferencias medidas. */
export function makeGpuResult(timings: Partial<BackendResult['timings']> = {}): BackendResult
{
  const base = {prepare_tiles_ms: 0.5, target_descriptors_ms: 0.5, matching_ms: 0.5, compose_ms: 1, total_ms: 5};
  const transfers = {transfer_h2d_ms: 1, transfer_d2h_ms: 1, staging_h2d_ms: 0.25, staging_d2h_ms: 0.25};
  return {...makeCpuResult(), backend: 'cuda', device: 'GPU de prueba', init_ms: 2, timings: {...base, ...transfers, ...timings}};
}
