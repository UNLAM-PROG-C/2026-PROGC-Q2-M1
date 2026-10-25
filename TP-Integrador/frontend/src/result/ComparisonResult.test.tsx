import {fireEvent, render, screen, within} from '@testing-library/react';
import {afterEach, describe, expect, it, vi} from 'vitest';
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

/**
 * jsdom no hace layout: el visor mediría 0 px y el mosaico se encajaría con escala 0.
 * Se le da al escenario el tamaño del mosaico, así el encaje es 1:1 y la escala visible es la del zoom.
 */
function stubStageSize(width: number, height: number): void
{
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(width);
  vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(height);
  vi.stubGlobal('ResizeObserver', class
  {
    constructor(private readonly callback: () => void)
    {
    }

    observe(): void
    {
      this.callback();
    }

    disconnect(): void
    {
    }
  });
}

afterEach(() =>
{
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

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
    stubStageSize(makeCpuResult().width, makeCpuResult().height);
    render(<ResultView job={makeJob({...COMPARISON, results: [makeGpuResult(), makeCpuResult()]})} dispatch={() => undefined} />);
    const [gpu, cpu] = images();
    expect(gpu.style.transform).toBe(cpu.style.transform);
    fireEvent.click(within(screen.getByRole('figure', {name: 'GPU — CUDA'})).getByRole('button', {name: 'Acercar'}));
    expect(gpu.style.transform).toContain(`scale(${ZOOM_STEP})`);
    expect(cpu.style.transform).toBe(gpu.style.transform);
  });

  it('el título es "Resultado", la bajada nombra los dos backends y cada mosaico su dispositivo (escenario "Título del resultado comparado")', () =>
  {
    render(<ResultView job={makeJob({...COMPARISON, results: [makeGpuResult(), makeCpuResult()]})} dispatch={() => undefined} />);
    expect(screen.getByRole('heading', {name: 'Resultado'})).toBeInTheDocument();
    expect(screen.getByText(/^GPU y CPU · .* px$/)).toBeInTheDocument();
    expect(within(screen.getByRole('figure', {name: 'GPU — CUDA'})).getByText('GPU — CUDA (GPU de prueba)')).toBeInTheDocument();
    expect(within(screen.getByRole('figure', {name: 'CPU'})).getByText('CPU (CPU de prueba)')).toBeInTheDocument();
  });

  it('cada mosaico descarga su propio archivo', () =>
  {
    render(<ResultView job={makeJob({...COMPARISON, results: [makeGpuResult(), makeCpuResult()]})} dispatch={() => undefined} />);
    const gpuLink = within(screen.getByRole('figure', {name: 'GPU — CUDA'})).getByText('PNG (sin pérdida)');
    const cpuLink = within(screen.getByRole('figure', {name: 'CPU'})).getByText('PNG (sin pérdida)');
    expect(gpuLink.getAttribute('href')).toMatch(/\/cuda\/png$/);
    expect(cpuLink.getAttribute('href')).toMatch(/\/cpu\/png$/);
  });

  it('si la GPU falló muestra solo el mosaico de CPU y el motivo', () =>
  {
    const failures = [{backend: 'cuda' as const, reason: 'memoria insuficiente en el dispositivo'}];
    render(<ResultView job={makeJob({...COMPARISON, results: [makeCpuResult()], failures})} dispatch={() => undefined} />);
    expect(within(screen.getByRole('group', {name: 'Acciones del paso'})).getByRole('alert')).toHaveTextContent('GPU falló: memoria insuficiente en el dispositivo');
    expect(screen.getAllByRole('img')).toHaveLength(1);
  });
});
