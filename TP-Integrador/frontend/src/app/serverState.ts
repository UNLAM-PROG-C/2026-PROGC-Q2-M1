// Estado del backend tal como lo ve esta pestaña: el snapshot de `/api/state`
// actualizado con los eventos del WebSocket. Es una función pura para poder
// testear cómo se aplica cada evento sin abrir conexiones.

import type {AppState, JobSnapshot, ServerEvent} from '../api/types';

type JobUpdate = (job: JobSnapshot) => JobSnapshot;

function updateJob(state: AppState, jobId: string, update: JobUpdate): AppState
{
  if (state.job?.job_id !== jobId)
  {
    return state;
  }
  return {...state, job: update(state.job)};
}

function applyJobEvent(state: AppState, event: ServerEvent): AppState
{
  switch (event.type)
  {
    case 'job_progress':
      return updateJob(state, event.job_id, (job) => ({...job, progress: {backend: event.backend, stage: event.stage, fraction: event.fraction}}));
    case 'load_finished':
      return updateJob(state, event.job_id, (job) => ({...job, load: event.load}));
    case 'backend_finished':
      return updateJob(state, event.job_id, (job) => ({...job, results: [...job.results, event.result]}));
    case 'backend_failed':
      return updateJob(state, event.job_id, (job) => ({...job, failures: [...job.failures, {backend: event.backend, reason: event.reason}]}));
    case 'comparison_finished':
      return updateJob(state, event.job_id, (job) => ({...job, verification: event.verification}));
    case 'job_finished':
      return updateJob(state, event.job_id, (job) => ({...job, status: 'finished'}));
    case 'job_failed':
      return updateJob(state, event.job_id, (job) => ({...job, status: 'failed', error: event.reason}));
    default:
      return state;
  }
}

/** Aplica un evento del servidor. Sin snapshot previo solo se acepta `state`. */
export function applyServerEvent(state: AppState | null, event: ServerEvent): AppState | null
{
  if (event.type === 'state')
  {
    return event.state;
  }
  if (state === null)
  {
    return null;
  }
  if (event.type === 'job_started')
  {
    return {...state, job: event.job};
  }
  if (event.type === 'worker_status')
  {
    return {...state, worker: event.worker};
  }
  return applyJobEvent(state, event);
}

/** Hay un trabajo ejecutándose (en esta pestaña o en otra). */
export function isJobRunning(state: AppState | null): boolean
{
  return state?.job?.status === 'running';
}
