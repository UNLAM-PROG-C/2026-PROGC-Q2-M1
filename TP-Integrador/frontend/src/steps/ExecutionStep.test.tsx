import {fireEvent, render, screen} from '@testing-library/react';
import {useReducer} from 'react';
import {describe, expect, it} from 'vitest';
import type {AppState} from '../api/types';
import {makeAppState, makeJob, makeWizard} from '../testing/fixtures';
import {wizardReducer, type WizardState} from '../wizard/wizardReducer';
import {gpuTitle, needsConfirmation, runBlocker} from './execution';
import {ExecutionStep} from './ExecutionStep';

function Harness({initial, server}: {initial: WizardState; server: AppState}): JSX.Element
{
  const [wizard, dispatch] = useReducer(wizardReducer, initial);
  return (
    <>
      <ExecutionStep wizard={wizard} dispatch={dispatch} server={server} connected />
      <output data-testid="mode">{wizard.mode}</output>
    </>
  );
}

function renderExecution(server: AppState): void
{
  render(<Harness initial={makeWizard({phase: 'execution'})} server={server} />);
}

const CUDA_GPU = {available: true, api: 'CUDA' as const, device: 'GeForce RTX 3060', reason: null};

describe('ExecutionStep', () =>
{
  it('sin GPU solo CPU es elegible y GPU muestra el motivo', () =>
  {
    renderExecution(makeAppState());
    const gpu = screen.getByRole('radio', {name: /GPU/});
    expect(gpu).toBeDisabled();
    expect(gpu).toHaveTextContent('no se detectó una GPU compatible');
    fireEvent.click(gpu);
    expect(screen.getByTestId('mode')).toHaveTextContent('cpu');
    expect(screen.getByRole('radio', {name: /CPU/})).toBeEnabled();
    expect(screen.getByRole('button', {name: 'Generar mosaico'})).toBeEnabled();
  });

  it('con CUDA la opción dice "GPU — CUDA (GeForce RTX 3060)" y se puede elegir', () =>
  {
    renderExecution(makeAppState({execution: {cpu: {available: true, device: null}, gpu: CUDA_GPU}}));
    const gpu = screen.getByRole('radio', {name: /GPU — CUDA \(GeForce RTX 3060\)/});
    fireEvent.click(gpu);
    expect(screen.getByTestId('mode')).toHaveTextContent('gpu');
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
});
