// Paso 5, estadísticas (design D5): un tile parchment con la tabla de tiempos
// y, en la barra fija, "Atrás" (al resultado) y "Volver a empezar". Si el
// trabajo se ejecutó con "Ambas" muestra la vista comparativa (cambio 4). La
// página scrollea normalmente y la barra queda siempre a la vista. Si el
// resultado ya no está, el título sigue siendo "Estadísticas" y el motivo va
// en la línea de mensajes (design D4 de consistencia-visual-del-stepper).

import type {Dispatch} from 'react';
import type {JobSnapshot} from '../api/types';
import {formatInt} from '../common/format';
import {StepActions} from '../components/StepActions';
import {StepTile} from '../components/StepTile';
import type {WizardAction} from '../wizard/wizardReducer';
import {ComparisonStats} from './ComparisonStats';
import {backendLabel} from './labels';
import {UNAVAILABLE_REASON} from './ResultView';
import {TimingsTable} from './TimingsTable';
import {singleTableRows} from './timings';

interface StatsPanelProps
{
  job: JobSnapshot | null;
  dispatch: Dispatch<WizardAction>;
}

function loadSummary(job: JobSnapshot): string
{
  const load = job.load;
  if (!load)
  {
    return '';
  }
  const skipped = load.skipped_files > 0 ? ` · ${formatInt(load.skipped_files)} archivos omitidos` : '';
  return `${formatInt(load.n_tiles)} teselas · ${formatInt(load.m_cells)} celdas (${formatInt(load.rows)} × ${formatInt(load.cols)})${skipped}`;
}

function StatsActions({dispatch, error}: {dispatch: Dispatch<WizardAction>; error?: string}): JSX.Element
{
  return <StepActions primaryLabel="Volver a empezar" onPrimary={() => dispatch({type: 'RESTART'})} onBack={() => dispatch({type: 'BACK'})} error={error} />;
}

export function StatsPanel({job, dispatch}: StatsPanelProps): JSX.Element
{
  if (!job)
  {
    return <StepTile title="Estadísticas" tone="parchment" actions={<StatsActions dispatch={dispatch} error={UNAVAILABLE_REASON} />} />;
  }
  return (
    <StepTile title="Estadísticas" tone="parchment" lead={loadSummary(job)} actions={<StatsActions dispatch={dispatch} />}>
      {job.mode === 'both'
        ? <ComparisonStats job={job} />
        : job.results.map((result) => (
          <TimingsTable key={result.backend} caption={backendLabel(result.backend, result.device)} columns={['Tiempo']} rows={singleTableRows(job.load, result)} />
        ))}
    </StepTile>
  );
}
