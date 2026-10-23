import {describe, expect, it} from 'vitest';
import {makeAppState, makeJob, makeRules, makeTarget, makeTiles, makeWizard} from '../testing/fixtures';
import {INITIAL_WIZARD_STATE, stepBlocker, wizardReducer, type WizardAction, type WizardState} from './wizardReducer';

function run(state: WizardState, ...actions: WizardAction[]): WizardState
{
  return actions.reduce(wizardReducer, state);
}

describe('wizardReducer: transiciones', () =>
{
  it('avanza images → params → execution y vuelve con BACK', () =>
  {
    const state = makeWizard();
    expect(run(state, {type: 'NEXT'}).phase).toBe('params');
    expect(run(state, {type: 'NEXT'}, {type: 'NEXT'}).phase).toBe('execution');
    expect(run(state, {type: 'NEXT'}, {type: 'NEXT'}, {type: 'BACK'}).phase).toBe('params');
  });

  it('NEXT no sale de execution: el trabajo empieza con JOB_STARTED', () =>
  {
    const state = makeWizard({phase: 'execution'});
    expect(run(state, {type: 'NEXT'}).phase).toBe('execution');
    const started = run(state, {type: 'JOB_STARTED', jobId: 'job-7'});
    expect(started).toMatchObject({phase: 'running', jobId: 'job-7'});
  });

  it('JOB_FINISHED y JOB_FAILED solo cierran el trabajo propio', () =>
  {
    const running = makeWizard({phase: 'running', jobId: 'job-1'});
    expect(run(running, {type: 'JOB_FINISHED', jobId: 'otro'}).phase).toBe('running');
    expect(run(running, {type: 'JOB_FINISHED', jobId: 'job-1'}).phase).toBe('result');
    expect(run(running, {type: 'JOB_FAILED', jobId: 'job-1'}).phase).toBe('result');
  });

  it('GO_TO solo permite volver a pasos anteriores', () =>
  {
    const state = makeWizard({phase: 'execution'});
    expect(run(state, {type: 'GO_TO', phase: 'images'}).phase).toBe('images');
    expect(run(makeWizard(), {type: 'GO_TO', phase: 'execution'}).phase).toBe('images');
  });

  it('volver atrás conserva subidas y forma de ejecución (escenario "Volver atrás")', () =>
  {
    const state = makeWizard({phase: 'execution', mode: 'gpu'});
    const after = run(state, {type: 'BACK'}, {type: 'PARAMS_CHANGED', patch: {cols: '150'}}, {type: 'NEXT'});
    expect(after).toMatchObject({phase: 'execution', mode: 'gpu', tiles: state.tiles, target: state.target});
    expect(after.params?.cols).toBe('150');
  });
});

describe('wizardReducer: "Siguiente" solo con datos válidos', () =>
{
  it('sin objetivo informa "falta la imagen objetivo" y no avanza', () =>
  {
    const state = makeWizard({target: null});
    expect(stepBlocker(state)).toBe('falta la imagen objetivo');
    expect(run(state, {type: 'NEXT'}).phase).toBe('images');
  });

  it('sin lote informa que falta el lote', () =>
  {
    expect(stepBlocker(makeWizard({tiles: null}))).toBe('falta el lote de teselas');
  });

  it('con columnas fuera de rango no avanza desde params', () =>
  {
    const state = run(makeWizard({phase: 'params'}), {type: 'PARAMS_CHANGED', patch: {cols: '401'}});
    expect(stepBlocker(state)).toMatch(/entre 1 y 400/);
    expect(run(state, {type: 'NEXT'}).phase).toBe('params');
  });

  it('descartar una imagen al reemplazarla bloquea solo hasta que se sube la nueva', () =>
  {
    const state = run(makeWizard(), {type: 'TARGET_DISCARDED'});
    expect(state.tiles).not.toBeNull();
    expect(stepBlocker(state)).toBe('falta la imagen objetivo');
    expect(stepBlocker(run(state, {type: 'TARGET_UPLOADED', target: makeTarget()}))).toBeNull();
  });
});

describe('wizardReducer: RESTART', () =>
{
  it('vuelve al paso 1 conservando tiles_id, target_id, parámetros y forma de ejecución', () =>
  {
    const result = run(makeWizard({phase: 'params', mode: 'gpu'}), {type: 'PARAMS_CHANGED', patch: {cols: '120', opacityPercent: 60}});
    const finished = {...result, phase: 'result' as const, jobId: 'job-1'};
    const restarted = run(finished, {type: 'RESTART'});
    expect(restarted).toMatchObject({phase: 'images', jobId: null, mode: 'gpu'});
    expect(restarted.tiles?.tiles_id).toBe('tiles-1');
    expect(restarted.target?.target_id).toBe('target-1');
    expect(restarted.params).toMatchObject({cols: '120', opacityPercent: 60});
  });

  it('no se puede reiniciar mientras corre un trabajo', () =>
  {
    expect(run(makeWizard({phase: 'running', jobId: 'job-1'}), {type: 'RESTART'}).phase).toBe('running');
  });
});

describe('wizardReducer: HYDRATE', () =>
{
  it('recupera las últimas subidas y los valores por defecto', () =>
  {
    const server = makeAppState({last_tiles: makeTiles(), last_target: makeTarget()});
    const state = run(INITIAL_WIZARD_STATE, {type: 'HYDRATE', state: server});
    expect(state).toMatchObject({phase: 'images', hydrated: true, tiles: makeTiles(), target: makeTarget()});
    expect(state.params?.cols).toBe('100');
  });

  it('con un trabajo en curso va directo al progreso (recarga durante un trabajo)', () =>
  {
    const server = makeAppState({job: makeJob({job_id: 'job-9', mode: 'cpu'})});
    expect(run(INITIAL_WIZARD_STATE, {type: 'HYDRATE', state: server})).toMatchObject({phase: 'running', jobId: 'job-9'});
  });

  it('con el último trabajo terminado muestra el resultado y recupera sus parámetros', () =>
  {
    const job = makeJob({status: 'finished', params: {cols: 80, tile_px: 64, alpha: 0.6, seed: 3, k: 5}});
    const state = run(INITIAL_WIZARD_STATE, {type: 'HYDRATE', state: makeAppState({job})});
    expect(state.phase).toBe('result');
    expect(state.params).toEqual({cols: '80', tilePx: 64, opacityPercent: 60, seed: '3'});
  });

  it('un snapshot posterior no saca a la pestaña del paso en el que está', () =>
  {
    const state = makeWizard({phase: 'execution'});
    const server = makeAppState({rules: makeRules(), job: makeJob({job_id: 'de-otra-pestana'})});
    expect(run(state, {type: 'HYDRATE', state: server}).phase).toBe('execution');
  });
});
