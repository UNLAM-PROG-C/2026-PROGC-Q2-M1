// Textos del paso 1, separados para testearlos sin DOM.

import {isZip} from '../api/client';
import type {TargetSummary, TilesSummary} from '../api/types';
import {formatInt} from '../common/format';

function plural(count: number, singular: string, pluralForm: string): string
{
  return `${formatInt(count)} ${count === 1 ? singular : pluralForm}`;
}

/** Por ejemplo "200 teselas · 3 archivos ignorados". */
export function tilesSummaryText(tiles: TilesSummary): string
{
  const parts = [plural(tiles.accepted, 'tesela', 'teselas')];
  if (tiles.ignored > 0)
  {
    parts.push(plural(tiles.ignored, 'archivo ignorado', 'archivos ignorados'));
  }
  if (tiles.rejected > 0)
  {
    parts.push(plural(tiles.rejected, 'entrada rechazada', 'entradas rechazadas'));
  }
  return parts.join(' · ');
}

export function targetSummaryText(target: TargetSummary): string
{
  return `${target.filename} · ${formatInt(target.width)} × ${formatInt(target.height)} px`;
}

/** Un lote es varias imágenes o un único zip; mezclar ambos no se admite. */
export function tilesSelectionError(files: File[]): string | null
{
  const zips = files.filter(isZip).length;
  return zips > 0 && files.length > 1 ? 'Subí varias imágenes o un único archivo .zip, no ambos.' : null;
}
