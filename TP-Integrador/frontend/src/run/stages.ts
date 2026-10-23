// Etapas que se muestran durante un trabajo y cómo se derivan sus barras a
// partir del snapshot (última etapa y fracción, design D5).

import type {JobProgressInfo, ProgressStage} from '../api/types';

export const STAGE_ORDER: readonly ProgressStage[] = ['load', 'prepare_tiles', 'target_descriptors', 'matching', 'compose', 'save'];

export const STAGE_LABELS: Readonly<Record<ProgressStage, string>> = {
  load: 'Carga común',
  prepare_tiles: 'Preparación de teselas',
  target_descriptors: 'Descriptores del objetivo',
  matching: 'Matching + top-k',
  compose: 'Composición',
  save: 'Guardando resultado',
};

/** Las etapas anteriores a la actual están completas; las posteriores, en cero. */
export function stageFractions(progress: JobProgressInfo | null): Record<ProgressStage, number>
{
  const current = progress ? STAGE_ORDER.indexOf(progress.stage) : -1;
  const entries = STAGE_ORDER.map((stage, index): [ProgressStage, number] =>
  {
    if (index < current)
    {
      return [stage, 1];
    }
    return [stage, index === current && progress ? progress.fraction : 0];
  });
  return Object.fromEntries(entries) as Record<ProgressStage, number>;
}
