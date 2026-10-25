// Contenido de la barra de acciones de un paso (design D3 del cambio
// consistencia-visual-del-stepper): "Atrás" (secundaria), la acción principal,
// una secundaria opcional (por ejemplo "Ver resultado" o "Volver a empezar") y
// debajo la línea de mensajes. La línea se renderiza siempre, aunque esté
// vacía, para que los botones no se muevan cuando aparece un mensaje. Muestra,
// por prioridad, un error del paso, el motivo por el que no se puede avanzar o
// una nota neutra.

import {PillButton} from './PillButton';

export interface StepLink
{
  label: string;
  onClick: () => void;
}

interface StepActionsProps
{
  primaryLabel: string;
  onPrimary: () => void;
  /** Motivo por el que no se puede avanzar: deshabilita la acción principal. */
  blocker?: string | null;
  /** Error general del paso (por ejemplo, el rechazo del trabajo). */
  error?: string | null;
  note?: string | null;
  onBack?: () => void;
  backLabel?: string;
  secondary?: StepLink;
}

const MESSAGE_ID = 'step-message';

function StepMessage({error, blocker, note}: Pick<StepActionsProps, 'error' | 'blocker' | 'note'>): JSX.Element
{
  const className = error ? 'step-actions__message step-actions__message--error' : 'step-actions__message';
  return (
    <p id={MESSAGE_ID} className={className} role={error ? 'alert' : undefined} aria-live="polite">
      {error ?? blocker ?? note}
    </p>
  );
}

export function StepActions(props: StepActionsProps): JSX.Element
{
  const {primaryLabel, onPrimary, blocker = null, onBack, backLabel = 'Atrás', secondary} = props;
  return (
    <div className="step-actions">
      <div className="step-actions__buttons">
        {onBack && <PillButton variant="secondary" onClick={onBack}>{backLabel}</PillButton>}
        <PillButton onClick={onPrimary} disabled={blocker !== null} aria-describedby={blocker ? MESSAGE_ID : undefined}>{primaryLabel}</PillButton>
        {secondary && <PillButton variant="secondary" onClick={secondary.onClick}>{secondary.label}</PillButton>}
      </div>
      <StepMessage error={props.error} blocker={blocker} note={props.note} />
    </div>
  );
}
