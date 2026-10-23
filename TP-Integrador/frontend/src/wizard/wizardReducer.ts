// Estado del stepper (patrón State, design D9 y D13): todas las transiciones
// válidas viven en este reducer puro, que se testea sin DOM.
//   images → params → execution → running → result
//   RESTART: result → images conservando subidas, parámetros y forma de ejecución.

import type {AppState, ExecutionMode, ParamRules, TargetSummary, TilesSummary} from '../api/types';
import {defaultDraft, draftFromParams, firstError, validateParams, type ParamDraft} from '../steps/params';

export type Phase = 'images' | 'params' | 'execution' | 'running' | 'result';

/** Pasos configurables del stepper, en orden. */
export const CONFIG_STEPS: readonly Phase[] = ['images', 'params', 'execution'];

export interface WizardState
{
  phase: Phase;
  hydrated: boolean;
  rules: ParamRules | null;
  tiles: TilesSummary | null;
  target: TargetSummary | null;
  params: ParamDraft | null;
  mode: ExecutionMode;
  jobId: string | null;
}

export type WizardAction =
  | {type: 'HYDRATE'; state: AppState}
  | {type: 'TILES_UPLOADED'; tiles: TilesSummary}
  | {type: 'TARGET_UPLOADED'; target: TargetSummary}
  | {type: 'TILES_DISCARDED'}
  | {type: 'TARGET_DISCARDED'}
  | {type: 'PARAMS_CHANGED'; patch: Partial<ParamDraft>}
  | {type: 'MODE_SELECTED'; mode: ExecutionMode}
  | {type: 'NEXT'}
  | {type: 'BACK'}
  | {type: 'GO_TO'; phase: Phase}
  | {type: 'JOB_STARTED'; jobId: string}
  | {type: 'JOB_FINISHED'; jobId: string}
  | {type: 'JOB_FAILED'; jobId: string}
  | {type: 'RESTART'};

export const INITIAL_WIZARD_STATE: WizardState = {
  phase: 'images',
  hydrated: false,
  rules: null,
  tiles: null,
  target: null,
  params: null,
  mode: 'cpu',
  jobId: null,
};

function imagesBlocker(state: WizardState): string | null
{
  if (!state.tiles)
  {
    return 'falta el lote de teselas';
  }
  if (state.tiles.accepted === 0)
  {
    return 'el lote no tiene teselas válidas';
  }
  return state.target ? null : 'falta la imagen objetivo';
}

function paramsBlocker(state: WizardState): string | null
{
  if (!state.rules || !state.params)
  {
    return 'esperando la conexión con el backend';
  }
  return firstError(validateParams(state.params, state.rules, state.target));
}

/** Motivo por el que no se puede avanzar desde el paso actual, o `null` si se puede. */
export function stepBlocker(state: WizardState): string | null
{
  if (state.phase === 'images')
  {
    return imagesBlocker(state);
  }
  if (state.phase === 'params')
  {
    return imagesBlocker(state) ?? paramsBlocker(state);
  }
  return null;
}

export function stepIndex(phase: Phase): number
{
  return CONFIG_STEPS.indexOf(phase);
}

function next(state: WizardState): WizardState
{
  const index = stepIndex(state.phase);
  const canMove = index >= 0 && index < CONFIG_STEPS.length - 1 && stepBlocker(state) === null;
  return canMove ? {...state, phase: CONFIG_STEPS[index + 1]} : state;
}

function back(state: WizardState): WizardState
{
  const index = stepIndex(state.phase);
  return index > 0 ? {...state, phase: CONFIG_STEPS[index - 1]} : state;
}

/** Solo se puede saltar a un paso ya visitado (anterior al actual). */
function goTo(state: WizardState, phase: Phase): WizardState
{
  const target = stepIndex(phase);
  return target >= 0 && target < stepIndex(state.phase) ? {...state, phase} : state;
}

function phaseForJob(state: AppState): Partial<WizardState>
{
  const job = state.job;
  if (!job)
  {
    return {};
  }
  const phase: Phase = job.status === 'running' ? 'running' : 'result';
  return {phase, jobId: job.job_id, mode: job.mode, params: draftFromParams(job.params)};
}

/** Primer snapshot: recupera últimas subidas y el trabajo en curso o terminado. */
function hydrate(state: WizardState, server: AppState): WizardState
{
  const rules = server.rules;
  if (state.hydrated)
  {
    return {...state, rules, params: state.params ?? defaultDraft(rules)};
  }
  const restored = {
    ...state,
    hydrated: true,
    rules,
    tiles: state.tiles ?? server.last_tiles,
    target: state.target ?? server.last_target,
    params: state.params ?? defaultDraft(rules),
  };
  return {...restored, ...phaseForJob(server)};
}

function jobEnded(state: WizardState, jobId: string): WizardState
{
  return state.phase === 'running' && state.jobId === jobId ? {...state, phase: 'result'} : state;
}

function editParams(state: WizardState, patch: Partial<ParamDraft>): WizardState
{
  return state.params ? {...state, params: {...state.params, ...patch}} : state;
}

export function wizardReducer(state: WizardState, action: WizardAction): WizardState
{
  switch (action.type)
  {
    case 'HYDRATE':
      return hydrate(state, action.state);
    case 'TILES_UPLOADED':
      return {...state, tiles: action.tiles};
    case 'TARGET_UPLOADED':
      return {...state, target: action.target};
    case 'TILES_DISCARDED':
      return {...state, tiles: null};
    case 'TARGET_DISCARDED':
      return {...state, target: null};
    case 'PARAMS_CHANGED':
      return editParams(state, action.patch);
    case 'MODE_SELECTED':
      return {...state, mode: action.mode};
    case 'NEXT':
      return next(state);
    case 'BACK':
      return back(state);
    case 'GO_TO':
      return goTo(state, action.phase);
    case 'JOB_STARTED':
      return state.phase === 'execution' ? {...state, phase: 'running', jobId: action.jobId} : state;
    case 'JOB_FINISHED':
    case 'JOB_FAILED':
      return jobEnded(state, action.jobId);
    case 'RESTART':
      return state.phase === 'result' ? {...state, phase: 'images', jobId: null} : state;
    default:
      return state;
  }
}
