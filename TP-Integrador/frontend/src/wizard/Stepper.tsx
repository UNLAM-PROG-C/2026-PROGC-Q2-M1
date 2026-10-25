// Franja fija del stepper con el estilo `sub-nav-frosted` (design D12): es la
// única navegación de la pantalla. Todo paso alcanzable (`canReach`), anterior
// o posterior, se puede abrir como `text-link`; el actual va en ink 600 y el
// resto apagado. Mientras se genera el mosaico, la posición 4 dice "Generando"
// y no hay links. Por debajo de 640 px el CSS muestra la versión compacta
// "Paso N de 5 · Nombre".

import type {Dispatch} from 'react';
import {canReach, stepIndex, WIZARD_STEPS, type Phase, type WizardAction, type WizardState} from './wizardReducer';

const STEP_NAMES: Readonly<Record<Phase, string>> = {
  images: 'Imágenes',
  params: 'Parámetros',
  execution: 'Ejecución',
  running: 'Generando',
  result: 'Resultado',
  stats: 'Estadísticas',
};

interface StepperProps
{
  wizard: WizardState;
  dispatch: Dispatch<WizardAction>;
}

function compactLabel(phase: Phase): string
{
  return `Paso ${stepIndex(phase) + 1} de ${WIZARD_STEPS.length} · ${STEP_NAMES[phase]}`;
}

function StepItem({step, wizard, dispatch}: {step: Phase; wizard: WizardState; dispatch: Dispatch<WizardAction>}): JSX.Element
{
  const index = stepIndex(step);
  const current = stepIndex(wizard.phase);
  if (index === current)
  {
    return <li className="stepper__step stepper__step--current" aria-current="step">{`${index + 1}. ${STEP_NAMES[wizard.phase]}`}</li>;
  }
  const label = `${index + 1}. ${STEP_NAMES[step]}`;
  const isLink = wizard.phase !== 'running' && canReach(wizard, step);
  return (
    <li className={index < current ? 'stepper__step stepper__step--done' : 'stepper__step'}>
      {isLink ? <button type="button" className="stepper__link" onClick={() => dispatch({type: 'GO_TO', phase: step})}>{label}</button> : label}
    </li>
  );
}

// Marca: isotipo de cuatro teselas (decorativo, oculto a lectores de pantalla)
// y la palabra con "Foto" liviano y "mosaico" semibold.
function Brand(): JSX.Element
{
  return (
    <span className="stepper__brand">
      <span className="stepper__mark" aria-hidden="true">
        <span className="stepper__tile" />
        <span className="stepper__tile stepper__tile--light" />
        <span className="stepper__tile stepper__tile--mid" />
        <span className="stepper__tile stepper__tile--ink" />
      </span>
      <span>
        <span className="stepper__brand-light">Foto</span>mosaico
      </span>
    </span>
  );
}

export function Stepper({wizard, dispatch}: StepperProps): JSX.Element
{
  return (
    <nav className="stepper" aria-label="Pasos">
      <Brand />
      <ol className="stepper__steps">
        {WIZARD_STEPS.map((step) => <StepItem key={step} step={step} wizard={wizard} dispatch={dispatch} />)}
      </ol>
      <span className="stepper__compact">{compactLabel(wizard.phase)}</span>
    </nav>
  );
}
