// Estado del stepper (patrón State, design D9 y D13): todas las transiciones
// válidas viven en este reducer puro, que se testea sin DOM.
//   images → params → execution → running → result → stats
//   NEXT, BACK y GO_TO se mueven en ambos sentidos entre los pasos alcanzables
//   (`canReach`); durante `running` no hay navegación.
//   RESTART: result/stats → images conservando subidas, parámetros y forma de ejecución.

import type {AppState, ExecutionMode, ParamRules, TargetSummary, TilesSummary} from '../api/types';
import {defaultDraft, draftFromParams, firstError, validateParams, type ParamDraft} from '../steps/params';

export type Phase = 'images' | 'params' | 'execution' | 'running' | 'result' | 'stats';

/** Pasos del stepper, en orden. `running` no es un paso: ocupa la posición de `result`. */
export const WIZARD_STEPS: readonly Phase[] = ['images', 'params', 'execution', 'result', 'stats'];

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
  /** El trabajo `jobId` terminó bien: habilita el paso de estadísticas. */
  resultReady: boolean;
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
  resultReady: false,
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
  return WIZARD_STEPS.indexOf(phase === 'running' ? 'result' : phase);
}

/** Si se puede abrir el paso `phase` con los datos actuales (design D2). */
export function canReach(state: WizardState, phase: Phase): boolean
{
  switch (phase)
  {
    case 'images':
      return true;
    case 'params':
      return imagesBlocker(state) === null;
    case 'execution':
      return imagesBlocker(state) === null && paramsBlocker(state) === null;
    case 'result':
      return state.jobId !== null;
    case 'stats':
      return state.resultReady;
    default:
      return false;
  }
}

/** Mientras se genera el mosaico el stepper no navega: al terminar lleva solo al resultado. */
function goTo(state: WizardState, phase: Phase): WizardState
{
  const canMove = state.phase !== 'running' && phase !== state.phase && canReach(state, phase);
  return canMove ? {...state, phase} : state;
}

function next(state: WizardState): WizardState
{
  const target = WIZARD_STEPS[stepIndex(state.phase) + 1];
  return target ? goTo(state, target) : state;
}

/** El paso anterior siempre se puede abrir: no depende de `canReach`. */
function back(state: WizardState): WizardState
{
  const target = WIZARD_STEPS[stepIndex(state.phase) - 1];
  return target && state.phase !== 'running' ? {...state, phase: target} : state;
}

function phaseForJob(state: AppState): Partial<WizardState>
{
  const job = state.job;
  if (!job)
  {
    return {};
  }
  const phase: Phase = job.status === 'running' ? 'running' : 'result';
  return {phase, jobId: job.job_id, resultReady: job.status === 'finished', mode: job.mode, params: draftFromParams(job.params)};
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

function jobEnded(state: WizardState, jobId: string, finished: boolean): WizardState
{
  return state.phase === 'running' && state.jobId === jobId ? {...state, phase: 'result', resultReady: finished} : state;
}

/**
 * El trabajo lo lanzó esta pestaña: se sigue aunque, mientras viajaba
 * `POST /api/jobs`, se haya navegado fuera de la ejecución (por ejemplo con
 * "Ver resultado"). Si no, correría en el worker sin que nadie lo muestre.
 */
function jobStarted(state: WizardState, jobId: string): WizardState
{
  return state.phase === 'running' ? state : {...state, phase: 'running', jobId, resultReady: false};
}

function restart(state: WizardState): WizardState
{
  const canRestart = state.phase === 'result' || state.phase === 'stats';
  return canRestart ? {...state, phase: 'images', jobId: null, resultReady: false} : state;
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
      return jobStarted(state, action.jobId);
    case 'JOB_FINISHED':
      return jobEnded(state, action.jobId, true);
    case 'JOB_FAILED':
      return jobEnded(state, action.jobId, false);
    case 'RESTART':
      return restart(state);
    default:
      return state;
  }
}
