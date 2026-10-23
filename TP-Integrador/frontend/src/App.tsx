// Pantalla única de la aplicación: el stepper arriba y debajo el contenido de
// la fase actual (pasos 1 a 3, ejecución y resultado). Sin sidebar ni menú.

import type {Dispatch} from 'react';
import type {AppState, JobSnapshot} from './api/types';
import {useServerState} from './app/useServerState';
import {ResultView} from './result/ResultView';
import {ProgressView} from './run/ProgressView';
import {ExecutionStep} from './steps/ExecutionStep';
import {ImagesStep} from './steps/ImagesStep';
import {ParamsStep} from './steps/ParamsStep';
import {Stepper} from './wizard/Stepper';
import {useWizard} from './wizard/useWizard';
import type {WizardAction, WizardState} from './wizard/wizardReducer';

interface PhaseProps
{
  wizard: WizardState;
  dispatch: Dispatch<WizardAction>;
  server: AppState | null;
  connected: boolean;
}

/** Trabajo del servidor que corresponde a esta pestaña (o `null` si es de otra). */
function ownJob(server: AppState | null, jobId: string | null): JobSnapshot | null
{
  const job = server?.job ?? null;
  return job && job.job_id === jobId ? job : null;
}

function PhaseContent(props: PhaseProps): JSX.Element
{
  const {wizard, dispatch, server} = props;
  switch (wizard.phase)
  {
    case 'images':
      return <ImagesStep wizard={wizard} dispatch={dispatch} />;
    case 'params':
      return <ParamsStep wizard={wizard} dispatch={dispatch} />;
    case 'execution':
      return <ExecutionStep {...props} />;
    case 'running':
      return <ProgressView job={ownJob(server, wizard.jobId)} />;
    case 'result':
      return <ResultView job={ownJob(server, wizard.jobId)} onRestart={() => dispatch({type: 'RESTART'})} />;
  }
}

function ConnectionBanner({connected}: {connected: boolean}): JSX.Element | null
{
  return connected ? null : <p className="connection-banner" role="status">Sin conexión con el backend: reintentando…</p>;
}

export function App(): JSX.Element
{
  const {server, connected} = useServerState();
  const {wizard, dispatch} = useWizard(server);
  return (
    <>
      <Stepper phase={wizard.phase} dispatch={dispatch} />
      <main className="app-main">
        <h1 className="visually-hidden">Fotomosaico</h1>
        <ConnectionBanner connected={connected} />
        <PhaseContent wizard={wizard} dispatch={dispatch} server={server} connected={connected} />
      </main>
    </>
  );
}
