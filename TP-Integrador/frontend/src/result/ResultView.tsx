// Pantalla de resultado: el mosaico como "el producto" sobre un tile oscuro de
// borde a borde con la única sombra del sistema, descarga, estadísticas a
// pedido y "Volver a empezar". Si el trabajo falló, muestra el motivo.

import {useState, type ReactNode} from 'react';
import {resultUrl} from '../api/client';
import type {BackendResult, JobSnapshot} from '../api/types';
import {formatInt} from '../common/format';
import {PillButton} from '../components/PillButton';
import {StepTile} from '../components/StepTile';
import {DownloadMenu} from './DownloadMenu';
import {backendLabel} from './labels';
import {MosaicViewer} from './MosaicViewer';
import {StatsPanel} from './StatsPanel';

interface ResultViewProps
{
  job: JobSnapshot | null;
  onRestart: () => void;
}

function FailedResult({reason, onRestart}: {reason: string; onRestart: () => void}): JSX.Element
{
  return (
    <StepTile title="No se pudo generar el mosaico" lead="Las imágenes siguen cargadas: podés volver a intentarlo.">
      <p className="field-error" role="alert">{reason}</p>
      <PillButton onClick={onRestart}>Volver a empezar</PillButton>
    </StepTile>
  );
}

function ProductTile({job, result, children}: {job: JobSnapshot; result: BackendResult; children: ReactNode}): JSX.Element
{
  const url = (kind: 'preview' | 'png'): string => resultUrl(job.job_id, result.backend, kind);
  return (
    <section className="product-tile" aria-label="Mosaico generado">
      <h2 className="product-tile__title">Tu mosaico</h2>
      <p className="product-tile__lead">{backendLabel(result.backend, result.device)} · {formatInt(result.width)} × {formatInt(result.height)} px</p>
      <MosaicViewer previewUrl={url('preview')} fullUrl={url('png')} width={result.width} height={result.height} alt="Fotomosaico generado" />
      {children}
    </section>
  );
}

function FinishedResult({job, onRestart}: {job: JobSnapshot; onRestart: () => void}): JSX.Element
{
  const [showStats, setShowStats] = useState(false);
  const result = job.results[0];
  return (
    <>
      <ProductTile job={job} result={result}>
        <div className="result-actions">
          <DownloadMenu jobId={job.job_id} backend={result.backend} />
          <PillButton variant="secondary" aria-expanded={showStats} onClick={() => setShowStats(!showStats)}>
            {showStats ? 'Ocultar estadísticas' : 'Ver estadísticas'}
          </PillButton>
          <PillButton variant="secondary" onClick={onRestart}>Volver a empezar</PillButton>
        </div>
      </ProductTile>
      {showStats && <StatsPanel job={job} />}
    </>
  );
}

export function ResultView({job, onRestart}: ResultViewProps): JSX.Element
{
  if (job?.status === 'failed')
  {
    return <FailedResult reason={job.error ?? 'el trabajo falló sin un motivo informado'} onRestart={onRestart} />;
  }
  if (!job)
  {
    // El backend conserva solo el último trabajo: si otra pestaña lanzó uno nuevo, este resultado ya no existe.
    return <FailedResult reason="este resultado ya no está disponible: se ejecutó otro trabajo" onRestart={onRestart} />;
  }
  if (job.results.length === 0)
  {
    return <StepTile title="Cargando el resultado…" tone="parchment">{null}</StepTile>;
  }
  return <FinishedResult job={job} onRestart={onRestart} />;
}
