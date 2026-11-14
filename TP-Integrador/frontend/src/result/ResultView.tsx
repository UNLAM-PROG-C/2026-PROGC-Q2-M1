// Paso 4, resultado (design D5 de consistencia-visual-del-stepper): el mosaico
// como "el producto" en un StepTile oscuro que ocupa el alto de la ventana
// (`fit`, design D3 de navegacion-por-pasos-y-estadisticas), con la única
// sombra del sistema sobre el visor. La descarga va junto al zoom de cada
// mosaico y la barra ofrece "Atrás", "Ver estadísticas" (la única acción
// principal: avanza al paso 5) y "Volver a empezar". Si el trabajo falló es el
// mismo paso oscuro, con el motivo en la línea de mensajes de la barra.
// En una comparación (cambio 4) los dos mosaicos van lado a lado con el zoom
// sincronizado: comparten un `ZoomController` (Observer). Si un backend falló,
// se muestra el otro mosaico y el motivo de la falla.

import {useState, type Dispatch} from 'react';
import {resultUrl} from '../api/client';
import type {BackendResult, JobSnapshot} from '../api/types';
import {formatInt} from '../common/format';
import {StepActions} from '../components/StepActions';
import {StepTile} from '../components/StepTile';
import type {WizardAction} from '../wizard/wizardReducer';
import {DownloadMenu} from './DownloadMenu';
import {backendKind, backendLabel, failureText} from './labels';
import {MosaicViewer} from './MosaicViewer';
import {ZoomController} from './zoomController';

// El backend conserva solo el último trabajo: si otra pestaña lanzó uno nuevo, este resultado ya no existe.
export const UNAVAILABLE_REASON = 'este resultado ya no está disponible: se ejecutó otro trabajo';

const RESULT_TITLE = 'Resultado';
const FAILED_LEAD = 'No se pudo generar el mosaico. Las imágenes siguen cargadas: podés volver a intentarlo.';
const LOADING_LEAD = 'Cargando el resultado…';

interface ResultViewProps
{
  job: JobSnapshot | null;
  dispatch: Dispatch<WizardAction>;
}

function RestartActions({dispatch, error}: {dispatch: Dispatch<WizardAction>; error?: string | null}): JSX.Element
{
  return <StepActions primaryLabel="Volver a empezar" onPrimary={() => dispatch({type: 'RESTART'})} onBack={() => dispatch({type: 'BACK'})} error={error} />;
}

export function FailedResult({reason, dispatch}: {reason: string; dispatch: Dispatch<WizardAction>}): JSX.Element
{
  return (
    <StepTile title={RESULT_TITLE} lead={FAILED_LEAD} tone="dark" fit actions={<RestartActions dispatch={dispatch} error={reason} />}>
      <div className="mosaic-placeholder">Sin mosaico</div>
    </StepTile>
  );
}

function resultLead(result: BackendResult): string
{
  return `${backendLabel(result.backend, result.device)} · ${formatInt(result.width)} × ${formatInt(result.height)} px`;
}

/** Por ejemplo "GPU y CPU · 4.000 × 3.000 px": los dos mosaicos tienen el mismo tamaño. */
function pairLead(results: BackendResult[]): string
{
  const kinds = results.map((result) => backendKind(result.backend)).join(' y ');
  return `${kinds} · ${formatInt(results[0].width)} × ${formatInt(results[0].height)} px`;
}

function Mosaic({job, result, zoom}: {job: JobSnapshot; result: BackendResult; zoom?: ZoomController}): JSX.Element
{
  const url = (kind: 'preview' | 'png'): string => resultUrl(job.job_id, result.backend, kind);
  const alt = `Fotomosaico generado en ${backendLabel(result.backend, null)}`;
  return (
    <MosaicViewer previewUrl={url('preview')} fullUrl={url('png')} width={result.width} height={result.height} alt={alt} zoom={zoom}>
      <DownloadMenu jobId={job.job_id} backend={result.backend} />
    </MosaicViewer>
  );
}

function MosaicPair({job}: {job: JobSnapshot}): JSX.Element
{
  const [zoom] = useState(() => new ZoomController());
  return (
    <div className="mosaic-pair">
      {job.results.map((result) => (
        <figure key={result.backend} className="mosaic-pair__item" aria-label={backendLabel(result.backend, null)}>
          <figcaption className="mosaic-pair__caption">{backendLabel(result.backend, result.device)}</figcaption>
          <Mosaic job={job} result={result} zoom={zoom} />
        </figure>
      ))}
    </div>
  );
}

/** Si un backend de la comparación falló, su motivo va a la línea de mensajes. */
function failuresText(job: JobSnapshot): string | null
{
  return job.failures.length === 0 ? null : job.failures.map((failure) => failureText(failure.backend, failure.reason)).join(' · ');
}

function ResultActions({job, dispatch}: ResultViewProps & {job: JobSnapshot}): JSX.Element
{
  const error = failuresText(job);
  if (job.status !== 'finished')
  {
    return <RestartActions dispatch={dispatch} error={error} />;
  }
  return (
    <StepActions primaryLabel="Ver estadísticas" onPrimary={() => dispatch({type: 'NEXT'})} onBack={() => dispatch({type: 'BACK'})} error={error}
      secondary={{label: 'Volver a empezar', onClick: () => dispatch({type: 'RESTART'})}} />
  );
}

function FinishedResult({job, dispatch}: ResultViewProps & {job: JobSnapshot}): JSX.Element
{
  const pair = job.results.length > 1;
  const lead = pair ? pairLead(job.results) : resultLead(job.results[0]);
  return (
    <StepTile title={RESULT_TITLE} lead={lead} tone="dark" fit actions={<ResultActions job={job} dispatch={dispatch} />}>
      {pair ? <MosaicPair job={job} /> : <Mosaic job={job} result={job.results[0]} />}
    </StepTile>
  );
}

export function ResultView({job, dispatch}: ResultViewProps): JSX.Element
{
  if (job?.status === 'failed')
  {
    return <FailedResult reason={job.error ?? 'el trabajo falló sin un motivo informado'} dispatch={dispatch} />;
  }
  if (!job)
  {
    return <FailedResult reason={UNAVAILABLE_REASON} dispatch={dispatch} />;
  }
  if (job.results.length === 0)
  {
    return <StepTile title={RESULT_TITLE} lead={LOADING_LEAD} tone="dark" fit actions={<RestartActions dispatch={dispatch} />} />;
  }
  return <FinishedResult job={job} dispatch={dispatch} />;
}
