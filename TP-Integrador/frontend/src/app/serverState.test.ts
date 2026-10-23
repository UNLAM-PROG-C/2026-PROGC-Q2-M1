import {describe, expect, it} from 'vitest';
import {makeAppState, makeCpuResult, makeJob} from '../testing/fixtures';
import {applyServerEvent, isJobRunning} from './serverState';

const CPU_RESULT = makeCpuResult();

describe('applyServerEvent', () =>
{
  it('el snapshot `state` reemplaza todo el estado', () =>
  {
    const snapshot = makeAppState({job: makeJob()});
    expect(applyServerEvent(null, {type: 'state', state: snapshot})).toBe(snapshot);
  });

  it('sin snapshot previo ignora los demás eventos', () =>
  {
    expect(applyServerEvent(null, {type: 'job_finished', job_id: 'job-1'})).toBeNull();
  });

  it('job_started marca el trabajo en curso en todas las pestañas', () =>
  {
    const state = applyServerEvent(makeAppState(), {type: 'job_started', job: makeJob()});
    expect(isJobRunning(state)).toBe(true);
  });

  it('aplica progreso, carga, resultado y fin al trabajo correspondiente', () =>
  {
    let state = applyServerEvent(makeAppState(), {type: 'job_started', job: makeJob()});
    state = applyServerEvent(state, {type: 'job_progress', job_id: 'job-1', backend: 'cpu', stage: 'matching', fraction: 0.5});
    expect(state?.job?.progress).toEqual({backend: 'cpu', stage: 'matching', fraction: 0.5});
    state = applyServerEvent(state, {type: 'backend_finished', job_id: 'job-1', result: CPU_RESULT});
    state = applyServerEvent(state, {type: 'job_finished', job_id: 'job-1'});
    expect(state?.job).toMatchObject({status: 'finished', results: [CPU_RESULT]});
    expect(isJobRunning(state)).toBe(false);
  });

  it('job_failed guarda el motivo', () =>
  {
    const state = applyServerEvent(makeAppState({job: makeJob()}), {type: 'job_failed', job_id: 'job-1', reason: 'memoria insuficiente en el dispositivo'});
    expect(state?.job).toMatchObject({status: 'failed', error: 'memoria insuficiente en el dispositivo'});
  });

  it('ignora eventos de otro trabajo', () =>
  {
    const before = makeAppState({job: makeJob()});
    expect(applyServerEvent(before, {type: 'job_finished', job_id: 'otro'})).toBe(before);
  });

  it('worker_status actualiza el estado del worker', () =>
  {
    const state = applyServerEvent(makeAppState(), {type: 'worker_status', worker: {ready: false, error: 'el worker se detuvo inesperadamente'}});
    expect(state?.worker).toEqual({ready: false, error: 'el worker se detuvo inesperadamente'});
  });
});
