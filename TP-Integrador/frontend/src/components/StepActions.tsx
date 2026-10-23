// Fila de acciones de un paso: "Atrás" (secundaria), la acción principal y,
// si no se puede avanzar, el motivo debajo (por ejemplo "falta la imagen objetivo").

import {PillButton} from './PillButton';

interface StepActionsProps
{
  primaryLabel: string;
  onPrimary: () => void;
  blocker: string | null;
  onBack?: () => void;
}

export function StepActions({primaryLabel, onPrimary, blocker, onBack}: StepActionsProps): JSX.Element
{
  return (
    <div className="step-actions">
      <div className="step-actions__buttons">
        {onBack && <PillButton variant="secondary" onClick={onBack}>Atrás</PillButton>}
        <PillButton onClick={onPrimary} disabled={blocker !== null} aria-describedby={blocker ? 'step-blocker' : undefined}>{primaryLabel}</PillButton>
      </div>
      {blocker && <p id="step-blocker" className="step-actions__blocker">{blocker}</p>}
    </div>
  );
}
