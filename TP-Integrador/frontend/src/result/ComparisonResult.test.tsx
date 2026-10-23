import {fireEvent, render, screen, within} from '@testing-library/react';
import {describe, expect, it, vi} from 'vitest';
import {makeCpuResult, makeGpuResult, makeJob} from '../testing/fixtures';
import {ResultView} from './ResultView';
import {ZOOM_STEP} from './zoom';
import {ZoomController} from './zoomController';

vi.mock('react-chartjs-2', () => ({Bar: () => <div data-testid="chart" />}));

const COMPARISON = {status: 'finished' as const, mode: 'both' as const, backends: ['cuda' as const, 'cpu' as const]};

function images(): HTMLElement[]
{
  return [screen.getByRole('img', {name: /GPU/}), screen.getByRole('img', {name: /CPU/})];
}

describe('resultado de una comparación', () =>
{
  it('el controlador avisa a todos los suscriptores y no avisa si la vista no cambió', () =>
  {
    const zoom = new ZoomController();
    const first = vi.fn();
    const second = vi.fn();
    zoom.subscribe(first);
    const unsubscribe = zoom.subscribe(second);
    zoom.update((view) => ({...view, scale: 2}));
    unsubscribe();
    zoom.update((view) => ({...view, scale: 3}));
    zoom.update((view) => view);
    expect(first).toHaveBeenCalledTimes(2);
    expect(second).toHaveBeenCalledTimes(1);
  });

  it('muestra los dos mosaicos lado a lado y acercar uno acerca el otro', () =>
  {
    render(<ResultView job={makeJob({...COMPARISON, results: [makeGpuResult(), makeCpuResult()]})} onRestart={() => undefined} />);
    const [gpu, cpu] = images();
    expect(gpu.style.transform).toBe(cpu.style.transform);
    fireEvent.click(within(screen.getByRole('figure', {name: 'GPU — CUDA'})).getByRole('button', {name: 'Acercar'}));
    expect(gpu.style.transform).toContain(`scale(${ZOOM_STEP})`);
    expect(cpu.style.transform).toBe(gpu.style.transform);
  });

  it('cada mosaico descarga su propio archivo', () =>
  {
    render(<ResultView job={makeJob({...COMPARISON, results: [makeGpuResult(), makeCpuResult()]})} onRestart={() => undefined} />);
    const gpuLink = within(screen.getByRole('figure', {name: 'GPU — CUDA'})).getByText('PNG (sin pérdida)');
    const cpuLink = within(screen.getByRole('figure', {name: 'CPU'})).getByText('PNG (sin pérdida)');
    expect(gpuLink.getAttribute('href')).toMatch(/\/cuda\/png$/);
    expect(cpuLink.getAttribute('href')).toMatch(/\/cpu\/png$/);
  });

  it('si la GPU falló muestra solo el mosaico de CPU y el motivo', () =>
  {
    const failures = [{backend: 'cuda' as const, reason: 'memoria insuficiente en el dispositivo'}];
    render(<ResultView job={makeJob({...COMPARISON, results: [makeCpuResult()], failures})} onRestart={() => undefined} />);
    expect(screen.getByRole('alert')).toHaveTextContent('GPU falló: memoria insuficiente en el dispositivo');
    expect(screen.getAllByRole('img')).toHaveLength(1);
  });
});
