// Información del problema (spec "Información del problema"): N, M, M·N y el
// tamaño de la imagen final, recalculados en vivo al cambiar los parámetros.

import {formatCount, formatInt, formatMegabytes} from '../common/format';
import type {ProblemInfo} from './params';

const NO_VALUE = '—';

interface ProblemInfoPanelProps
{
  info: ProblemInfo | null;
  n: number;
}

function Row({term, value}: {term: string; value: string}): JSX.Element
{
  return (
    <div className="problem-info__row">
      <dt>{term}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export function ProblemInfoPanel({info, n}: ProblemInfoPanelProps): JSX.Element
{
  const grid = info ? `${formatInt(info.m)} (${formatInt(info.rows)} filas × ${formatInt(info.cols)} columnas)` : NO_VALUE;
  const size = info ? `${formatInt(info.width)} × ${formatInt(info.height)} px · ${formatMegabytes(info.bytes)} sin comprimir` : NO_VALUE;
  return (
    <dl className="problem-info" aria-label="Información del problema">
      <Row term="Teselas válidas (N)" value={formatInt(n)} />
      <Row term="Celdas de la grilla (M)" value={grid} />
      <Row term="Comparaciones de distancia (M·N)" value={info ? formatCount(info.pairs) : NO_VALUE} />
      <Row term="Imagen final" value={size} />
    </dl>
  );
}
