import {fireEvent, render, screen, within} from '@testing-library/react';
import {useReducer} from 'react';
import {describe, expect, it, vi} from 'vitest';
import {createJob} from '../api/client';
import type {AppState} from '../api/types';
import {makeAppState, makeJob, makeWizard} from '../testing/fixtures';
import {wizardReducer, type WizardState} from '../wizard/wizardReducer';
import {gpuTitle, needsConfirmation, runBlocker} from './execution';
import {ExecutionStep} from './ExecutionStep';

vi.mock('../api/client', async (importOriginal) => ({...await importOriginal<typeof import('../api/client')>(), createJob: vi.fn()}));

function Harness({initial, server}: {initial: WizardState; server: AppState}): JSX.Element
{
  const [wizard, dispatch] = useReducer(wizardReducer, initial);
  return (
    <>
      <ExecutionStep wizard={wizard} dispatch={dispatch} server={server} connected />
      <output data-testid="mode">{wizard.mode}</output>
      <output data-testid="phase">{wizard.phase}</output>
    </>
  );
}

function renderExecution(server: AppState, jobId: string | null = null): void
{
  render(<Harness initial={makeWizard({phase: 'execution', jobId})} server={server} />);
}

const CUDA_GPU = {available: true, api: 'CUDA' as const, device: 'GeForce RTX 3060', reason: null};
const BOTH_AVAILABLE = {available: true, reason: null};
const SLOW_CALIBRATION = {matching_ns_per_pair: 10000, prepare_ns_per_pixel: 1, compose_ns_per_pixel: 1};

function actionBar(): HTMLElement
{
  return screen.getByRole('group', {name: 'Acciones del paso'});
}

describe('ExecutionStep', () =>
{
  it('sin GPU solo CPU es elegible y GPU muestra el motivo', () =>
  {
    renderExecution(makeAppState());
    const gpu = screen.getByRole('radio', {name: /^GPU/});
    expect(gpu).toBeDisabled();
    expect(gpu).toHaveTextContent('no se detectó una GPU compatible');
    fireEvent.click(gpu);
    expect(screen.getByTestId('mode')).toHaveTextContent('cpu');
    expect(screen.getByRole('radio', {name: /^CPU/})).toBeEnabled();
    expect(screen.getByRole('button', {name: 'Generar mosaico'})).toBeEnabled();
  });

  it('con CUDA la opción dice "GPU — CUDA (GeForce RTX 3060)" y se puede elegir', () =>
  {
    renderExecution(makeAppState({execution: {cpu: {available: true, device: null}, gpu: CUDA_GPU, both: BOTH_AVAILABLE}}));
    const gpu = screen.getByRole('radio', {name: /GPU — CUDA \(GeForce RTX 3060\)/});
    fireEvent.click(gpu);
    expect(screen.getByTestId('mode')).toHaveTextContent('gpu');
  });

  it('sin GPU "Ambas" no es elegible y muestra el motivo', () =>
  {
    renderExecution(makeAppState());
    const both = screen.getByRole('radio', {name: /Ambas \(CPU y GPU\)/});
    expect(both).toBeDisabled();
    expect(both).toHaveTextContent('no se detectó una GPU compatible');
    fireEvent.click(both);
    expect(screen.getByTestId('mode')).toHaveTextContent('cpu');
  });

  it('con GPU "Ambas" se puede elegir y pide confirmación como CPU', () =>
  {
    const calibration = {matching_ns_per_pair: 10000, prepare_ns_per_pixel: 1, compose_ns_per_pixel: 1};
    const execution = {cpu: {available: true, device: null}, gpu: CUDA_GPU, both: BOTH_AVAILABLE};
    renderExecution(makeAppState({execution, calibration}));
    const both = screen.getByRole('radio', {name: /Ambas/});
    fireEvent.click(both);
    expect(screen.getByTestId('mode')).toHaveTextContent('both');
    expect(both).toHaveTextContent(/CPU: tiempo estimado/);
    fireEvent.click(screen.getByRole('button', {name: 'Generar mosaico'}));
    expect(screen.getByRole('alertdialog', {name: 'Confirmar trabajo largo'})).toBeInTheDocument();
  });

  it('con OpenCL indica la API y el dispositivo', () =>
  {
    expect(gpuTitle({available: true, api: 'OpenCL', device: 'Radeon RX 6600', reason: null})).toBe('GPU — OpenCL (Radeon RX 6600)');
  });

  it('con un trabajo en curso (de otra pestaña) "Generar mosaico" queda deshabilitado', () =>
  {
    renderExecution(makeAppState({job: makeJob({job_id: 'de-otra-pestana'})}));
    expect(screen.getByRole('button', {name: 'Generar mosaico'})).toBeDisabled();
    expect(screen.getByText('hay un trabajo en curso')).toBeInTheDocument();
  });

  it('vuelve a habilitarse cuando el trabajo termina o falla', () =>
  {
    expect(runBlocker(makeAppState({job: makeJob({status: 'finished'})}), true, 'cpu')).toBeNull();
    expect(runBlocker(makeAppState({job: makeJob({status: 'failed'})}), true, 'cpu')).toBeNull();
  });

  it('con un resultado de esta pestaña ofrece "Ver resultado" y pasa al paso 4 sin lanzar otro trabajo', () =>
  {
    renderExecution(makeAppState({job: makeJob({job_id: 'job-1', status: 'finished'})}), 'job-1');
    fireEvent.click(screen.getByRole('button', {name: 'Ver resultado'}));
    expect(screen.getByTestId('phase')).toHaveTextContent('result');
  });

  it('sin un resultado de esta pestaña no ofrece "Ver resultado" (escenario "Sin resultado")', () =>
  {
    renderExecution(makeAppState({job: makeJob({job_id: 'de-otra-pestana', status: 'finished'})}));
    expect(screen.queryByRole('button', {name: 'Ver resultado'})).not.toBeInTheDocument();
  });

  it('pide confirmación si la estimación de CPU supera el umbral', () =>
  {
    const calibration = {matching_ns_per_pair: 10000, prepare_ns_per_pixel: 1, compose_ns_per_pixel: 1};
    const server = makeAppState({calibration});
    expect(needsConfirmation(server, makeWizard({phase: 'execution'}))).toBe(true);
    renderExecution(server);
    expect(screen.getByText(/CPU: tiempo estimado ~\d+ min/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: 'Generar mosaico'}));
    expect(screen.getByRole('alertdialog', {name: 'Confirmar trabajo largo'})).toBeInTheDocument();
  });

  it('la confirmación usa la misma barra: "Cancelar" vuelve a "Generar mosaico" sin lanzar el trabajo', () =>
  {
    renderExecution(makeAppState({calibration: SLOW_CALIBRATION}));
    fireEvent.click(screen.getByRole('button', {name: 'Generar mosaico'}));
    const dialog = within(actionBar()).getByRole('alertdialog', {name: 'Confirmar trabajo largo'});
    expect(dialog).toHaveTextContent(/puede tardar ~\d+ min/);
    fireEvent.click(within(dialog).getByRole('button', {name: 'Cancelar'}));
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Generar mosaico'})).toBeEnabled();
    expect(createJob).not.toHaveBeenCalled();
  });

  it('si el servidor rechaza el trabajo, el motivo aparece en la barra (escenario "Error al lanzar el trabajo")', async () =>
  {
    vi.mocked(createJob).mockRejectedValueOnce(new Error('el servidor rechazó el trabajo'));
    renderExecution(makeAppState());
    fireEvent.click(screen.getByRole('button', {name: 'Generar mosaico'}));
    expect(await within(actionBar()).findByRole('alert')).toHaveTextContent('el servidor rechazó el trabajo');
  });

  it('ordena "Atrás", "Generar mosaico" y "Ver resultado" (escenario "Orden de las acciones")', () =>
  {
    renderExecution(makeAppState({job: makeJob({job_id: 'job-1', status: 'finished'})}), 'job-1');
    const labels = within(actionBar()).getAllByRole('button').map((button) => button.textContent);
    expect(labels).toEqual(['Atrás', 'Generar mosaico', 'Ver resultado']);
  });

  it('si otra pestaña lanza un trabajo, un rechazo anterior se descarta y no vuelve cuando ese trabajo termina', async () =>
  {
    vi.mocked(createJob).mockRejectedValueOnce(new Error('ya hay un trabajo en curso'));
    const initial = makeWizard({phase: 'execution'});
    const {rerender} = render(<Harness initial={initial} server={makeAppState()} />);
    fireEvent.click(screen.getByRole('button', {name: 'Generar mosaico'}));
    expect(await within(actionBar()).findByRole('alert')).toHaveTextContent('ya hay un trabajo en curso');
    rerender(<Harness initial={initial} server={makeAppState({job: makeJob({job_id: 'de-otra-pestana'})})} />);
    expect(within(actionBar()).queryByRole('alert')).not.toBeInTheDocument();
    expect(within(actionBar()).getByText('hay un trabajo en curso')).toBeInTheDocument();
    rerender(<Harness initial={initial} server={makeAppState({job: makeJob({job_id: 'de-otra-pestana', status: 'finished'})})} />);
    expect(within(actionBar()).queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Generar mosaico'})).toBeEnabled();
  });

  it('una confirmación tapada por el trabajo de otra pestaña no reaparece sola', () =>
  {
    const initial = makeWizard({phase: 'execution'});
    const {rerender} = render(<Harness initial={initial} server={makeAppState({calibration: SLOW_CALIBRATION})} />);
    fireEvent.click(screen.getByRole('button', {name: 'Generar mosaico'}));
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    rerender(<Harness initial={initial} server={makeAppState({calibration: SLOW_CALIBRATION, job: makeJob({job_id: 'de-otra-pestana'})})} />);
    rerender(<Harness initial={initial} server={makeAppState({calibration: SLOW_CALIBRATION, job: makeJob({job_id: 'de-otra-pestana', status: 'finished'})})} />);
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Generar mosaico'})).toBeEnabled();
  });
});
