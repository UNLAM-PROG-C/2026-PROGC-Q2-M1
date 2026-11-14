// Etapas que se muestran durante un trabajo y cómo se derivan sus barras a
// partir del snapshot (última etapa y fracción, design D5). En una comparación
// (cambio 4) cada backend tiene sus barras, en el orden de ejecución.

import type {BackendName, JobProgressInfo, JobSnapshot, ProgressStage} from '../api/types';

export const STAGE_ORDER: readonly ProgressStage[] = ['load', 'prepare_tiles', 'target_descriptors', 'matching', 'compose', 'save'];

/** Etapas propias de cada backend (todas menos la carga común). */
export const BACKEND_STAGES: readonly ProgressStage[] = STAGE_ORDER.filter((stage) => stage !== 'load');

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

/** Barras de un backend dentro de un trabajo; `failure` es el motivo si falló. */
export interface BackendProgress
{
  backend: BackendName;
  fractions: Record<ProgressStage, number>;
  failure: string | null;
}

const COMPLETE_STAGES = Object.fromEntries(STAGE_ORDER.map((stage) => [stage, 1])) as Record<ProgressStage, number>;

/** Avance de la carga común: completa en cuanto algún backend empezó. */
export function loadFraction(progress: JobProgressInfo | null): number
{
  if (!progress)
  {
    return 0;
  }
  return progress.stage === 'load' ? progress.fraction : 1;
}

/** Los backends ya terminados (o anteriores al actual) completos, el actual según el snapshot y los siguientes en cero. */
export function backendProgress(job: JobSnapshot): BackendProgress[]
{
  const progress = job.progress;
  const current = progress?.backend ? job.backends.indexOf(progress.backend) : -1;
  return job.backends.map((backend, index) =>
  {
    const failure = job.failures.find((item) => item.backend === backend)?.reason ?? null;
    const done = index < current || job.results.some((result) => result.backend === backend);
    const fractions = done ? COMPLETE_STAGES : stageFractions(index === current ? progress : null);
    return {backend, fractions, failure};
  });
}
