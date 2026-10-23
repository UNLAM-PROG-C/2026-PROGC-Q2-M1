// Estadísticas de una ejecución con "Ambas" (design D5 del cambio 4): banda de
// verificación arriba, gráfico agrupado CPU vs. GPU y tabla con una columna por
// backend y una de speedup. Si la GPU falló, solo los tiempos de CPU con el
// aviso "sin comparación".

import type {BackendName, BackendResult, CellDifferences, JobSnapshot, Verification} from '../api/types';
import {formatInt} from '../common/format';
import {ComparisonChart} from './ComparisonChart';
import {BACKEND_SHORT_NAMES, backendLabel, failureText} from './labels';
import {TimingsTable} from './TimingsTable';
import {comparisonRows, singleTableRows} from './timings';

export const IDENTICAL_TEXT = 'Resultados idénticos ✓';
export const NO_COMPARISON_TEXT = 'sin comparación';

function differenceText(backend: BackendName, diff: CellDifferences, reference: BackendName): string
{
  const cells = diff.total_cells === 1 ? '1 celda difiere' : `${formatInt(diff.total_cells)} celdas difieren`;
  return `${BACKEND_SHORT_NAMES[backend]}: ${cells} de ${BACKEND_SHORT_NAMES[reference]} (diferencias de punto flotante en casi-empates)`;
}

/** Por ejemplo "OpenCL: 3 celdas difieren de CPU (diferencias de punto flotante en casi-empates)". */
export function differenceTexts(verification: Verification): string[]
{
  const entries = Object.entries(verification.differences) as [BackendName, CellDifferences][];
  return entries.filter(([, diff]) => diff.total_cells > 0).map(([backend, diff]) => differenceText(backend, diff, verification.reference));
}

function bandLines(job: JobSnapshot): {text: string; differs: boolean}[]
{
  if (job.failures.length > 0)
  {
    return job.failures.map((failure) => ({text: `${failureText(failure.backend, failure.reason)} · ${NO_COMPARISON_TEXT}`, differs: true}));
  }
  if (!job.verification)
  {
    return [];
  }
  return job.verification.identical
    ? [{text: IDENTICAL_TEXT, differs: false}]
    : differenceTexts(job.verification).map((text) => ({text, differs: true}));
}

function VerificationBand({job}: {job: JobSnapshot}): JSX.Element | null
{
  const lines = bandLines(job);
  if (lines.length === 0)
  {
    return null;
  }
  return (
    <div className="verification-band" role="status">
      {lines.map(({text, differs}) => <p key={text} className={differs ? 'verification-band__difference' : undefined}>{text}</p>)}
    </div>
  );
}

function SideBySide({job, cpu, gpu}: {job: JobSnapshot; cpu: BackendResult; gpu: BackendResult}): JSX.Element
{
  const columns = [backendLabel(cpu.backend, cpu.device), backendLabel(gpu.backend, gpu.device), 'Speedup GPU'];
  return (
    <>
      <ComparisonChart cpu={cpu} gpu={gpu} />
      <TimingsTable caption="Tiempos por etapa" columns={columns} rows={comparisonRows(job.load, cpu, gpu)} />
    </>
  );
}

export function ComparisonStats({job}: {job: JobSnapshot}): JSX.Element
{
  const cpu = job.results.find((result) => result.backend === 'cpu');
  const gpu = job.results.find((result) => result.backend !== 'cpu');
  const single = job.results.map((result) => (
    <TimingsTable key={result.backend} caption={backendLabel(result.backend, result.device)} columns={['Tiempo']} rows={singleTableRows(job.load, result)} />
  ));
  return (
    <>
      <VerificationBand job={job} />
      {cpu && gpu ? <SideBySide job={job} cpu={cpu} gpu={gpu} /> : single}
    </>
  );
}
