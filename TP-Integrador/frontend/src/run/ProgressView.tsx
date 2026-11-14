// Progreso del trabajo en curso ("Generando", igual que el stepper): una barra
// por etapa sobre un tile parchment, actualizada por los eventos
// `job_progress` del WebSocket. En una comparación
// (cambio 4) la carga común va primero y después un grupo de barras por
// backend, en el orden en que se ejecutan (GPU y después CPU).

import type {JobSnapshot, ProgressStage} from '../api/types';
import {formatPercent} from '../common/format';
import {ProgressBar} from '../components/ProgressBar';
import {StepTile} from '../components/StepTile';
import {backendLabel, failureText} from '../result/labels';
import {BACKEND_STAGES, backendProgress, loadFraction, STAGE_LABELS, type BackendProgress} from './stages';

// Durante la generación no hay navegación: la barra solo explica qué pasa al terminar.
const DONE_NOTE = 'Al terminar se abre el resultado.';

interface ProgressViewProps
{
  job: JobSnapshot | null;
}

function runningLabel(job: JobSnapshot | null): string
{
  const backend = job?.progress?.backend ?? job?.backends[0];
  return backend ? `Ejecutando en ${backendLabel(backend, null)}.` : 'Iniciando el trabajo…';
}

function StageRow({stage, fraction}: {stage: ProgressStage; fraction: number}): JSX.Element
{
  return (
    <li className="stage-list__item">
      <span className="stage-list__label">{STAGE_LABELS[stage]}</span>
      <ProgressBar label={STAGE_LABELS[stage]} fraction={fraction} />
      <span className="stage-list__value">{formatPercent(fraction)}</span>
    </li>
  );
}

function BackendStages({progress}: {progress: BackendProgress}): JSX.Element
{
  const label = backendLabel(progress.backend, null);
  return (
    <section className="stage-group" aria-label={label}>
      <h3 className="stage-group__title">{label}</h3>
      {progress.failure
        ? <p className="field-error" role="alert">{failureText(progress.backend, progress.failure)}</p>
        : <ol className="stage-list">{BACKEND_STAGES.map((stage) => <StageRow key={stage} stage={stage} fraction={progress.fractions[stage]} />)}</ol>}
    </section>
  );
}

export function ProgressView({job}: ProgressViewProps): JSX.Element
{
  const backends = job ? backendProgress(job) : [];
  const single = backends.length <= 1;
  const singleStages = single ? BACKEND_STAGES.map((stage) => <StageRow key={stage} stage={stage} fraction={backends[0]?.fractions[stage] ?? 0} />) : null;
  return (
    <StepTile title="Generando" tone="parchment" lead={runningLabel(job)} actions={<p className="step-bar__note">{DONE_NOTE}</p>}>
      <ol className="stage-list">
        <StageRow stage="load" fraction={loadFraction(job?.progress ?? null)} />
        {singleStages}
      </ol>
      {!single && backends.map((progress) => <BackendStages key={progress.backend} progress={progress} />)}
    </StepTile>
  );
}
