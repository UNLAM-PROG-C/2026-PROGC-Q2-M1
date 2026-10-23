// Hook del stepper: el reducer de wizardReducer.ts sincronizado con el estado
// del backend (primer snapshot y fin del trabajo que lanzó esta pestaña).

import {useEffect, useReducer, type Dispatch} from 'react';
import type {AppState} from '../api/types';
import {INITIAL_WIZARD_STATE, wizardReducer, type WizardAction, type WizardState} from './wizardReducer';

export interface Wizard
{
  wizard: WizardState;
  dispatch: Dispatch<WizardAction>;
}

export function useWizard(server: AppState | null): Wizard
{
  const [wizard, dispatch] = useReducer(wizardReducer, INITIAL_WIZARD_STATE);
  const job = server?.job ?? null;

  useEffect(() =>
  {
    if (server)
    {
      dispatch({type: 'HYDRATE', state: server});
    }
    // Solo los snapshots completos traen reglas nuevas: el resto de los eventos conserva la referencia.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [server?.rules]);

  // Re-evalúa también al cambiar de fase: el trabajo puede terminar antes de que llegue la respuesta de POST /api/jobs.
  useEffect(() =>
  {
    if (job?.status === 'finished' || job?.status === 'failed')
    {
      dispatch({type: job.status === 'finished' ? 'JOB_FINISHED' : 'JOB_FAILED', jobId: job.job_id});
    }
  }, [job?.status, job?.job_id, wizard.phase, wizard.jobId]);

  return {wizard, dispatch};
}
