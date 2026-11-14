// Gráfico de barras agrupadas CPU vs. GPU con Chart.js (design D5): una
// categoría por etapa comparada, las transferencias y el total. Un interruptor
// cambia el eje Y entre escala lineal y logarítmica; arranca en logarítmica si
// la GPU es tanto más rápida que en lineal sus barras no se verían.
// Los colores y la tipografía salen de `tokens.css`: GPU en el acento y CPU en
// gris, sin grilla decorativa.

import {BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, LogarithmicScale, Tooltip, type ChartData, type ChartOptions} from 'chart.js';
import {useState} from 'react';
import {Bar} from 'react-chartjs-2';
import type {BackendResult} from '../api/types';
import {CHART_CATEGORIES, prefersLogScale, seriesValues} from './chartData';
import {backendKind} from './labels';

ChartJS.register(CategoryScale, LinearScale, LogarithmicScale, BarElement, Legend, Tooltip);

// Mismas convenciones numéricas que el resto de la interfaz ("10.000").
const CHART_LOCALE = 'es-AR';

type BarChartData =ChartData<'bar', (number | null)[], string>;

interface ComparisonChartProps
{
  cpu: BackendResult;
  gpu: BackendResult;
}

function cssToken(name: string): string
{
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** En escala logarítmica el cero no tiene lugar: queda sin barra. */
function forScale(values: (number | null)[], logarithmic: boolean): (number | null)[]
{
  return logarithmic ? values.map((value) => (value !== null && value > 0 ? value : null)) : values;
}

function chartData(cpu: BackendResult, gpu: BackendResult, logarithmic: boolean): BarChartData
{
  const series = [{result: gpu, color: cssToken('--color-primary')}, {result: cpu, color: cssToken('--color-ink-muted-48')}];
  return {
    labels: CHART_CATEGORIES.map((category) => category.label),
    datasets: series.map(({result, color}) => ({label: backendKind(result.backend), data: forScale(seriesValues(result), logarithmic), backgroundColor: color})),
  };
}

function chartOptions(logarithmic: boolean): ChartOptions<'bar'>
{
  const font = {family: cssToken('--font-text'), size: Number.parseFloat(cssToken('--type-caption-size'))};
  const color = cssToken('--color-ink-muted-80');
  const title = logarithmic ? 'Tiempo (ms, escala logarítmica)' : 'Tiempo (ms)';
  return {
    locale: CHART_LOCALE,
    responsive: true,
    maintainAspectRatio: false,
    plugins: {legend: {labels: {font, color}}},
    scales: {
      x: {grid: {display: false}, ticks: {font, color}},
      y: {type: logarithmic ? 'logarithmic' : 'linear', grid: {display: false}, ticks: {font, color}, title: {display: true, text: title, font, color}},
    },
  };
}

export function ComparisonChart({cpu, gpu}: ComparisonChartProps): JSX.Element
{
  const [logarithmic, setLogarithmic] = useState(() => prefersLogScale([seriesValues(cpu), seriesValues(gpu)]));
  return (
    <figure className="comparison-chart">
      <label className="comparison-chart__switch">
        <input type="checkbox" role="switch" checked={logarithmic} onChange={(event) => setLogarithmic(event.target.checked)} />
        Escala logarítmica
      </label>
      <div className="comparison-chart__canvas">
        <Bar data={chartData(cpu, gpu, logarithmic)} options={chartOptions(logarithmic)} aria-label="Tiempo por etapa en CPU y GPU" role="img" />
      </div>
    </figure>
  );
}
