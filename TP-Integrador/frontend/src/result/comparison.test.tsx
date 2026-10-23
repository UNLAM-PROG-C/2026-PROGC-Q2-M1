import {fireEvent, render, screen} from '@testing-library/react';
import {describe, expect, it, vi} from 'vitest';
import type {JobSnapshot} from '../api/types';
import {makeCpuResult, makeGpuResult, makeJob} from '../testing/fixtures';
import {prefersLogScale, seriesValues} from './chartData';
import {ComparisonStats, IDENTICAL_TEXT} from './ComparisonStats';
import {formatSpeedup, speedup, speedupText} from './speedup';
import {comparisonRows} from './timings';

// jsdom no tiene canvas: el gráfico se reemplaza por un resumen de lo que recibiría Chart.js.
vi.mock('react-chartjs-2', () => ({
  Bar: ({options}: {options: {scales: {y: {type: string; title: {text: string}}}}}) => (
    <div data-testid="chart" data-scale={options.scales.y.type}>{options.scales.y.title.text}</div>
  ),
}));

const CPU_MATCHING_MS = 30_000;
const GPU_MATCHING_MS = 150;

function comparisonJob(overrides: Partial<JobSnapshot> = {}): JobSnapshot
{
  const cpu = makeCpuResult();
  const slowCpu = {...cpu, timings: {...cpu.timings, matching_ms: CPU_MATCHING_MS, total_ms: CPU_MATCHING_MS + 10}};
  const gpu = makeGpuResult({matching_ms: GPU_MATCHING_MS, total_ms: GPU_MATCHING_MS + 5});
  const verification = {reference: 'cpu' as const, identical: true, differences: {cuda: {topk_cells: 0, image_cells: 0, total_cells: 0}}};
  return makeJob({status: 'finished', mode: 'both', backends: ['cuda', 'cpu'], results: [gpu, slowCpu], verification, ...overrides});
}

describe('speedup', () =>
{
  it('30.000 ms en CPU contra 150 ms en GPU se muestra como "200×"', () =>
  {
    expect(speedup(CPU_MATCHING_MS, GPU_MATCHING_MS)).toBe(200);
    expect(speedupText(CPU_MATCHING_MS, GPU_MATCHING_MS)).toBe('200×');
  });

  it('un tiempo faltante o cero muestra "—"', () =>
  {
    expect(speedupText(null, GPU_MATCHING_MS)).toBe('—');
    expect(speedupText(CPU_MATCHING_MS, undefined)).toBe('—');
    expect(speedupText(CPU_MATCHING_MS, 0)).toBe('—');
  });

  it('por debajo de 10× muestra un decimal', () =>
  {
    expect(formatSpeedup(3.46)).toBe('3,5×');
  });

  it('la tabla comparativa tiene CPU, GPU y speedup; las transferencias no se comparan', () =>
  {
    const [gpu, cpu] = comparisonJob().results;
    const rows = comparisonRows(null, cpu, gpu);
    expect(rows.find((row) => row.label === 'Matching + top-k')?.values).toEqual(['30.000,0 ms', '150,0 ms', '200×']);
    expect(rows.find((row) => row.label === 'Transferencia host→device: DMA')?.values).toEqual(['no aplica', '1,0 ms', '—']);
  });
});

describe('estadísticas comparativas', () =>
{
  it('muestran "Resultados idénticos ✓", el gráfico y una columna por backend', () =>
  {
    render(<ComparisonStats job={comparisonJob()} />);
    expect(screen.getByRole('status')).toHaveTextContent(IDENTICAL_TEXT);
    expect(screen.getByRole('columnheader', {name: 'Speedup GPU'})).toBeInTheDocument();
    expect(screen.getByRole('columnheader', {name: /GPU — CUDA/})).toBeInTheDocument();
  });

  it('con una razón mayor a 100 el eje arranca en escala logarítmica y se puede pasar a lineal', () =>
  {
    const [gpu, cpu] = comparisonJob().results;
    expect(prefersLogScale([seriesValues(cpu), seriesValues(gpu)])).toBe(true);
    render(<ComparisonStats job={comparisonJob()} />);
    expect(screen.getByTestId('chart')).toHaveAttribute('data-scale', 'logarithmic');
    expect(screen.getByTestId('chart')).toHaveTextContent('escala logarítmica');
    fireEvent.click(screen.getByRole('switch', {name: 'Escala logarítmica'}));
    expect(screen.getByTestId('chart')).toHaveAttribute('data-scale', 'linear');
  });

  it('informa las celdas que difieren de CPU', () =>
  {
    const verification = {reference: 'cpu' as const, identical: false, differences: {opencl: {topk_cells: 3, image_cells: 1, total_cells: 3}}};
    render(<ComparisonStats job={comparisonJob({verification})} />);
    expect(screen.getByRole('status')).toHaveTextContent('OpenCL: 3 celdas difieren de CPU (diferencias de punto flotante en casi-empates)');
  });

  it('si la GPU falló muestra solo los tiempos de CPU con el aviso "sin comparación"', () =>
  {
    const failures = [{backend: 'cuda' as const, reason: 'memoria insuficiente en el dispositivo'}];
    render(<ComparisonStats job={comparisonJob({results: [makeCpuResult()], failures, verification: null})} />);
    expect(screen.getByRole('status')).toHaveTextContent('GPU falló: memoria insuficiente en el dispositivo · sin comparación');
    expect(screen.queryByTestId('chart')).toBeNull();
    expect(screen.getByRole('table', {name: /CPU/})).toBeInTheDocument();
  });
});
