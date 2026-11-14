// Paso 3: forma de ejecución (CPU, GPU o Ambas) según el hardware que informa el
// backend, estimación de CPU con confirmación y lanzamiento del trabajo.
// Mientras haya un trabajo en curso (de cualquier pestaña) no se puede ejecutar.
// Si esta pestaña ya generó un mosaico, "Ver resultado" lo abre sin lanzar otro.

import {useEffect, useState, type Dispatch} from 'react';
import {createJob} from '../api/client';
import type {AppState, ExecutionMode} from '../api/types';
import {formatEstimate} from '../common/format';
import {OptionCard} from '../components/OptionCard';
import {StepActions, type StepLink} from '../components/StepActions';
import {StepTile} from '../components/StepTile';
import {canReach, type WizardAction, type WizardState} from '../wizard/wizardReducer';
import {buildJobRequest, cpuEstimateSeconds, gpuTitle, needsConfirmation, NO_GPU_REASON, runBlocker} from './execution';

interface ExecutionStepProps
{
  wizard: WizardState;
  dispatch: Dispatch<WizardAction>;
  server: AppState | null;
  connected: boolean;
}

/** Detalle de cada tarjeta: estimación de CPU o motivo por el que no está disponible. */
function modeDetails(server: AppState | null, wizard: WizardState): Record<ExecutionMode, string | null | undefined>
{
  const {gpu, both} = server?.execution ?? {};
  const seconds = cpuEstimateSeconds(server, wizard);
  const estimate = seconds === null ? undefined : `CPU: tiempo estimado ${formatEstimate(seconds)}`;
  return {
    cpu: estimate ?? server?.execution.cpu.device,
    gpu: gpu?.available ? undefined : (gpu?.reason ?? NO_GPU_REASON),
    both: both?.available ? estimate : (both?.reason ?? NO_GPU_REASON),
  };
}

function ModeCards({wizard, dispatch, server}: ExecutionStepProps): JSX.Element
{
  const select = (mode: ExecutionMode) => () => dispatch({type: 'MODE_SELECTED', mode});
  const {gpu, both} = server?.execution ?? {};
  const details = modeDetails(server, wizard);
  return (
    <div className="mode-cards" role="radiogroup" aria-label="Forma de ejecución">
      <OptionCard title="CPU" selected={wizard.mode === 'cpu'} onSelect={select('cpu')} detail={details.cpu} />
      <OptionCard title={gpu ? gpuTitle(gpu) : 'GPU'} selected={wizard.mode === 'gpu' && Boolean(gpu?.available)} disabled={!gpu?.available}
        onSelect={select('gpu')} detail={details.gpu} />
      <OptionCard title="Ambas (CPU y GPU)" selected={wizard.mode === 'both' && Boolean(both?.available)} disabled={!both?.available}
        onSelect={select('both')} detail={details.both} />
    </div>
  );
}

/** La confirmación ocupa la misma barra que las acciones: los botones no cambian de lugar (design D3). */
function ConfirmLongRun({seconds, onConfirm, onCancel}: {seconds: number; onConfirm: () => void; onCancel: () => void}): JSX.Element
{
  const warning = `La ejecución en CPU puede tardar ${formatEstimate(seconds)}. Mientras tanto no se puede lanzar otro trabajo.`;
  return (
    <div className="step-actions-dialog" role="alertdialog" aria-label="Confirmar trabajo largo">
      <StepActions primaryLabel="Generar igual" onPrimary={onConfirm} onBack={onCancel} backLabel="Cancelar" note={warning} />
    </div>
  );
}

/**
 * `blocked`: hay un bloqueo externo (otro trabajo en curso, sin conexión). Un
 * rechazo anterior del servidor ya no describe la situación: se descarta, para
 * que la línea de mensajes muestre el bloqueo y no reaparezca al terminar.
 */
function useStartJob(wizard: WizardState, dispatch: Dispatch<WizardAction>, blocked: boolean): {start: () => void; error: string | null; sending: boolean}
{
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  useEffect(() =>
  {
    if (blocked)
    {
      setError(null);
    }
  }, [blocked]);
  const start = (): void =>
  {
    const request = buildJobRequest(wizard);
    if (!request)
    {
      return;
    }
    setSending(true);
    setError(null);
    createJob(request)
      .then((created) => dispatch({type: 'JOB_STARTED', jobId: created.job_id}))
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setSending(false));
  };
  return {start, error, sending};
}

function lastResultLink(wizard: WizardState, dispatch: Dispatch<WizardAction>): StepLink | undefined
{
  return canReach(wizard, 'result') ? {label: 'Ver resultado', onClick: () => dispatch({type: 'NEXT'})} : undefined;
}

function ExecutionActions(props: ExecutionStepProps & {onRun: () => void; blocker: string | null; error: string | null}): JSX.Element
{
  const {wizard, dispatch, onRun, blocker, error} = props;
  return (
    <StepActions primaryLabel="Generar mosaico" onPrimary={onRun} onBack={() => dispatch({type: 'BACK'})} blocker={blocker} error={error}
      secondary={lastResultLink(wizard, dispatch)} />
  );
}

/** Una confirmación que quedó tapada por un bloqueo externo no vuelve a aparecer sola cuando se libera. */
function useConfirmation(blocked: boolean): [boolean, (confirming: boolean) => void]
{
  const [confirming, setConfirming] = useState(false);
  useEffect(() =>
  {
    if (blocked)
    {
      setConfirming(false);
    }
  }, [blocked]);
  return [confirming, setConfirming];
}

export function ExecutionStep(props: ExecutionStepProps): JSX.Element
{
  const {wizard, server, connected} = props;
  const externalBlocker = runBlocker(server, connected, wizard.mode);
  const [confirming, setConfirming] = useConfirmation(externalBlocker !== null);
  const job = useStartJob(wizard, props.dispatch, externalBlocker !== null);
  const blocker = job.sending ? 'enviando el trabajo…' : externalBlocker;
  const onRun = (): void => (needsConfirmation(server, wizard) ? setConfirming(true) : job.start());
  const onConfirm = (): void =>
  {
    setConfirming(false);
    job.start();
  };
  const actions = confirming && blocker === null
    ? <ConfirmLongRun seconds={cpuEstimateSeconds(server, wizard) ?? 0} onCancel={() => setConfirming(false)} onConfirm={onConfirm} />
    : <ExecutionActions {...props} onRun={onRun} blocker={blocker} error={job.error} />;
  return (
    <StepTile title="Ejecución" lead="Elegí dónde se calcula el mosaico." actions={actions}>
      <ModeCards {...props} />
    </StepTile>
  );
}
