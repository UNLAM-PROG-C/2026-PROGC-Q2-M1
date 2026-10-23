// Franja fija del stepper con el estilo `sub-nav-frosted` (design D12): es la
// única navegación de la pantalla. Los pasos completos se pueden volver a
// abrir (como `text-link`), el actual va en ink 600 y los futuros apagados.
// Por debajo de 640 px el CSS muestra la versión compacta "Paso N de 3 · Nombre".

import type {Dispatch} from 'react';
import {CONFIG_STEPS, stepIndex, type Phase, type WizardAction} from './wizardReducer';

const STEP_NAMES: Readonly<Record<Phase, string>> = {
  images: 'Imágenes',
  params: 'Parámetros',
  execution: 'Ejecución',
  running: 'Generando',
  result: 'Resultado',
};

interface StepperProps
{
  phase: Phase;
  dispatch: Dispatch<WizardAction>;
}

function compactLabel(phase: Phase): string
{
  const index = stepIndex(phase);
  return index >= 0 ? `Paso ${index + 1} de ${CONFIG_STEPS.length} · ${STEP_NAMES[phase]}` : STEP_NAMES[phase];
}

function StepItem({step, phase, dispatch}: {step: Phase; phase: Phase; dispatch: Dispatch<WizardAction>}): JSX.Element
{
  const index = stepIndex(step);
  const current = stepIndex(phase);
  const label = `${index + 1}. ${STEP_NAMES[step]}`;
  if (step === phase)
  {
    return <li className="stepper__step stepper__step--current" aria-current="step">{label}</li>;
  }
  const done = current < 0 || index < current;
  const canReturn = current >= 0 && index < current;
  return (
    <li className={done ? 'stepper__step stepper__step--done' : 'stepper__step'}>
      {canReturn ? <button type="button" className="stepper__link" onClick={() => dispatch({type: 'GO_TO', phase: step})}>{label}</button> : label}
    </li>
  );
}

export function Stepper({phase, dispatch}: StepperProps): JSX.Element
{
  return (
    <nav className="stepper" aria-label="Pasos">
      <span className="stepper__brand">Fotomosaico</span>
      <ol className="stepper__steps">
        {CONFIG_STEPS.map((step) => <StepItem key={step} step={step} phase={phase} dispatch={dispatch} />)}
      </ol>
      <span className="stepper__compact">{compactLabel(phase)}</span>
    </nav>
  );
}
