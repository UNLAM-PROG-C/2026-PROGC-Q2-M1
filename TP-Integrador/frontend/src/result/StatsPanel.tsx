// Panel de estadísticas: solo aparece al apretar "Ver estadísticas", en un
// tile parchment debajo del resultado. El cambio 4 le agrega la vista comparativa.

import type {JobSnapshot} from '../api/types';
import {formatInt} from '../common/format';
import {StepTile} from '../components/StepTile';
import {backendLabel} from './labels';
import {TimingsTable} from './TimingsTable';

interface StatsPanelProps
{
  job: JobSnapshot;
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

export function StatsPanel({job}: StatsPanelProps): JSX.Element
{
  return (
    <StepTile title="Estadísticas" tone="parchment" lead={loadSummary(job)}>
      {job.results.map((result) => (
        <TimingsTable key={result.backend} load={job.load} result={result} caption={backendLabel(result.backend, result.device)} />
      ))}
    </StepTile>
  );
}
