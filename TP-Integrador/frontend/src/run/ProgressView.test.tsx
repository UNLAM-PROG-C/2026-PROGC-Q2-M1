import {render, screen, within} from '@testing-library/react';
import {describe, expect, it} from 'vitest';
import {makeGpuResult, makeJob} from '../testing/fixtures';
import {ProgressView} from './ProgressView';
import {backendProgress} from './stages';

const COMPARISON = {mode: 'both' as const, backends: ['cuda' as const, 'cpu' as const]};

describe('progreso de una comparación', () =>
{
  it('GPU terminada y CPU en curso: la GPU completa y la CPU avanza', () =>
  {
    const job = makeJob({...COMPARISON, results: [makeGpuResult()], progress: {backend: 'cpu', stage: 'matching', fraction: 0.4}});
    const [gpu, cpu] = backendProgress(job);
    expect(Object.values(gpu.fractions).every((fraction) => fraction === 1)).toBe(true);
    expect(cpu.fractions).toMatchObject({prepare_tiles: 1, target_descriptors: 1, matching: 0.4, compose: 0});
    render(<ProgressView job={job} />);
    const cpuGroup = screen.getByRole('region', {name: 'CPU'});
    expect(within(cpuGroup).getByText('40 %')).toBeInTheDocument();
    expect(within(screen.getByRole('region', {name: 'GPU — CUDA'})).getAllByText('100 %')).toHaveLength(5);
  });

  it('la falla de la GPU se muestra con su motivo y la CPU sigue', () =>
  {
    const failures = [{backend: 'cuda' as const, reason: 'memoria insuficiente en el dispositivo'}];
    render(<ProgressView job={makeJob({...COMPARISON, failures, progress: {backend: 'cpu', stage: 'compose', fraction: 0.5}})} />);
    expect(screen.getByRole('alert')).toHaveTextContent('GPU falló: memoria insuficiente en el dispositivo');
    expect(within(screen.getByRole('region', {name: 'CPU'})).getByText('50 %')).toBeInTheDocument();
  });

  it('con un solo backend se ve una sola lista de etapas', () =>
  {
    render(<ProgressView job={makeJob({progress: {backend: 'cpu', stage: 'matching', fraction: 0.5}})} />);
    expect(screen.getAllByRole('listitem')).toHaveLength(6);
    expect(screen.queryByRole('region', {name: 'CPU'})).toBeNull();
  });
});
