// Progreso del trabajo en curso: una barra por etapa sobre un tile parchment,
// actualizada por los eventos `job_progress` del WebSocket.

import type {JobSnapshot} from '../api/types';
import {formatPercent} from '../common/format';
import {ProgressBar} from '../components/ProgressBar';
import {StepTile} from '../components/StepTile';
import {backendLabel} from '../result/labels';
import {STAGE_LABELS, STAGE_ORDER, stageFractions} from './stages';

interface ProgressViewProps
{
  job: JobSnapshot | null;
}

function runningLabel(job: JobSnapshot | null): string
{
  const backend = job?.progress?.backend ?? job?.backends[0];
  return backend ? `Ejecutando en ${backendLabel(backend, null)}.` : 'Iniciando el trabajo…';
}

export function ProgressView({job}: ProgressViewProps): JSX.Element
{
  const fractions = stageFractions(job?.progress ?? null);
  return (
    <StepTile title="Generando el mosaico" tone="parchment" lead={runningLabel(job)}>
      <ol className="stage-list">
        {STAGE_ORDER.map((stage) => (
          <li key={stage} className="stage-list__item">
            <span className="stage-list__label">{STAGE_LABELS[stage]}</span>
            <ProgressBar label={STAGE_LABELS[stage]} fraction={fractions[stage]} />
            <span className="stage-list__value">{formatPercent(fractions[stage])}</span>
          </li>
        ))}
      </ol>
    </StepTile>
  );
}
