// Paso 3: forma de ejecución (CPU, GPU o Ambas) según el hardware que informa el
// backend, estimación de CPU con confirmación y lanzamiento del trabajo.
// Mientras haya un trabajo en curso (de cualquier pestaña) no se puede ejecutar.

import {useState, type Dispatch} from 'react';
import {createJob} from '../api/client';
import type {AppState, ExecutionMode} from '../api/types';
import {formatEstimate} from '../common/format';
import {OptionCard} from '../components/OptionCard';
import {PillButton} from '../components/PillButton';
import {StepActions} from '../components/StepActions';
import {StepTile} from '../components/StepTile';
import type {WizardAction, WizardState} from '../wizard/wizardReducer';
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

function ConfirmLongRun({seconds, onConfirm, onCancel}: {seconds: number; onConfirm: () => void; onCancel: () => void}): JSX.Element
{
  return (
    <div className="confirm-panel" role="alertdialog" aria-label="Confirmar trabajo largo">
      <p>La ejecución en CPU puede tardar {formatEstimate(seconds)}. Mientras tanto no se puede lanzar otro trabajo.</p>
      <div className="confirm-panel__buttons">
        <PillButton variant="secondary" onClick={onCancel}>Cancelar</PillButton>
        <PillButton onClick={onConfirm}>Generar igual</PillButton>
      </div>
    </div>
  );
}

function useStartJob(wizard: WizardState, dispatch: Dispatch<WizardAction>): {start: () => void; error: string | null; sending: boolean}
{
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
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

export function ExecutionStep(props: ExecutionStepProps): JSX.Element
{
  const {wizard, dispatch, server, connected} = props;
  const [confirming, setConfirming] = useState(false);
  const job = useStartJob(wizard, dispatch);
  const blocker = job.sending ? 'enviando el trabajo…' : runBlocker(server, connected, wizard.mode);
  const onRun = (): void => (needsConfirmation(server, wizard) ? setConfirming(true) : job.start());
  return (
    <StepTile title="Ejecución" lead="Elegí dónde se calcula el mosaico.">
      <ModeCards {...props} />
      {job.error && <p className="field-error" role="alert">{job.error}</p>}
      {confirming && blocker === null
        ? <ConfirmLongRun seconds={cpuEstimateSeconds(server, wizard) ?? 0} onCancel={() => setConfirming(false)} onConfirm={job.start} />
        : <StepActions primaryLabel="Generar mosaico" onPrimary={onRun} onBack={() => dispatch({type: 'BACK'})} blocker={blocker} />}
    </StepTile>
  );
}
