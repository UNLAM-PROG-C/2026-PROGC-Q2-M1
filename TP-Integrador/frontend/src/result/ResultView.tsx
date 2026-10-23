// Pantalla de resultado: el mosaico como "el producto" sobre un tile oscuro de
// borde a borde con la única sombra del sistema, descarga, estadísticas a
// pedido y "Volver a empezar". Si el trabajo falló, muestra el motivo.
// En una comparación (cambio 4) los dos mosaicos van lado a lado con el zoom
// sincronizado: comparten un `ZoomController` (Observer). Si un backend falló,
// se muestra el otro mosaico y el motivo de la falla.

import {useState, type ReactNode} from 'react';
import {resultUrl} from '../api/client';
import type {BackendResult, JobSnapshot} from '../api/types';
import {formatInt} from '../common/format';
import {PillButton} from '../components/PillButton';
import {StepTile} from '../components/StepTile';
import {DownloadMenu} from './DownloadMenu';
import {backendLabel, failureText} from './labels';
import {MosaicViewer} from './MosaicViewer';
import {StatsPanel} from './StatsPanel';
import {ZoomController} from './zoomController';

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

function resultLead(result: BackendResult): string
{
  return `${backendLabel(result.backend, result.device)} · ${formatInt(result.width)} × ${formatInt(result.height)} px`;
}

function Mosaic({job, result, zoom}: {job: JobSnapshot; result: BackendResult; zoom?: ZoomController}): JSX.Element
{
  const url = (kind: 'preview' | 'png'): string => resultUrl(job.job_id, result.backend, kind);
  const alt = `Fotomosaico generado en ${backendLabel(result.backend, null)}`;
  return <MosaicViewer previewUrl={url('preview')} fullUrl={url('png')} width={result.width} height={result.height} alt={alt} zoom={zoom} />;
}

function Failures({job}: {job: JobSnapshot}): JSX.Element | null
{
  if (job.failures.length === 0)
  {
    return null;
  }
  return <>{job.failures.map((failure) => <p key={failure.backend} className="product-tile__failure" role="alert">{failureText(failure.backend, failure.reason)}</p>)}</>;
}

function SingleTile({job, children}: {job: JobSnapshot; children: ReactNode}): JSX.Element
{
  const result = job.results[0];
  return (
    <section className="product-tile" aria-label="Mosaico generado">
      <h2 className="product-tile__title">Tu mosaico</h2>
      <p className="product-tile__lead">{resultLead(result)}</p>
      <Failures job={job} />
      <Mosaic job={job} result={result} />
      <div className="result-actions">
        <DownloadMenu jobId={job.job_id} backend={result.backend} />
        {children}
      </div>
    </section>
  );
}

function PairTile({job, children}: {job: JobSnapshot; children: ReactNode}): JSX.Element
{
  const [zoom] = useState(() => new ZoomController());
  return (
    <section className="product-tile" aria-label="Mosaicos generados">
      <h2 className="product-tile__title">Tus mosaicos</h2>
      <div className="mosaic-pair">
        {job.results.map((result) => (
          <figure key={result.backend} className="mosaic-pair__item" aria-label={backendLabel(result.backend, null)}>
            <figcaption className="product-tile__lead">{resultLead(result)}</figcaption>
            <Mosaic job={job} result={result} zoom={zoom} />
            <DownloadMenu jobId={job.job_id} backend={result.backend} />
          </figure>
        ))}
      </div>
      <div className="result-actions">{children}</div>
    </section>
  );
}

function FinishedResult({job, onRestart}: {job: JobSnapshot; onRestart: () => void}): JSX.Element
{
  const [showStats, setShowStats] = useState(false);
  const Tile = job.results.length > 1 ? PairTile : SingleTile;
  return (
    <>
      <Tile job={job}>
        <PillButton variant="secondary" aria-expanded={showStats} onClick={() => setShowStats(!showStats)}>
          {showStats ? 'Ocultar estadísticas' : 'Ver estadísticas'}
        </PillButton>
        <PillButton variant="secondary" onClick={onRestart}>Volver a empezar</PillButton>
      </Tile>
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
