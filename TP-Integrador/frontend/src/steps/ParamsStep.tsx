// Paso 2: parámetros del mosaico con ayuda contextual, validación junto a cada
// campo (con las reglas de /api/state) e información del problema en vivo.
// El límite de salida no es de un campo: va en la línea de mensajes de la barra.

import type {Dispatch} from 'react';
import {StepActions} from '../components/StepActions';
import {StepTile} from '../components/StepTile';
import {stepBlocker, type WizardAction, type WizardState} from '../wizard/wizardReducer';
import {ColsControl, OpacityControl, SeedControl, TilePxControl, type ParamChange} from './ParamControls';
import {draftProblemInfo, validateParams, type ParamErrors} from './params';
import {ProblemInfoPanel} from './ProblemInfoPanel';

interface ParamsStepProps
{
  wizard: WizardState;
  dispatch: Dispatch<WizardAction>;
}

// El detalle de un error de campo ya está junto al campo: la barra solo avisa por qué no se avanza.
const FIELD_ERRORS_BLOCKER = 'corregí los campos marcados';

function ParamsActions({wizard, dispatch, errors}: ParamsStepProps & {errors?: ParamErrors}): JSX.Element
{
  const blocker = errors?.cols || errors?.seed ? FIELD_ERRORS_BLOCKER : stepBlocker(wizard);
  return <StepActions primaryLabel="Siguiente" onPrimary={() => dispatch({type: 'NEXT'})} onBack={() => dispatch({type: 'BACK'})} blocker={blocker} error={errors?.output} />;
}

export function ParamsStep({wizard, dispatch}: ParamsStepProps): JSX.Element
{
  const {params, rules} = wizard;
  if (!params || !rules)
  {
    return <StepTile title="Parámetros" lead="Conectando con el backend…" actions={<ParamsActions wizard={wizard} dispatch={dispatch} />} />;
  }
  const errors = validateParams(params, rules, wizard.target);
  const onChange: ParamChange = (patch) => dispatch({type: 'PARAMS_CHANGED', patch});
  const controlProps = {draft: params, rules, errors, onChange};
  return (
    <StepTile title="Parámetros" lead="Elegí cómo se arma el mosaico." actions={<ParamsActions wizard={wizard} dispatch={dispatch} errors={errors} />}>
      <div className="params-step">
        <ColsControl {...controlProps} />
        <TilePxControl {...controlProps} />
        <OpacityControl {...controlProps} />
        <SeedControl {...controlProps} />
      </div>
      <ProblemInfoPanel info={errors.cols ? null : draftProblemInfo(wizard.tiles, wizard.target, params)} n={wizard.tiles?.accepted ?? 0} />
    </StepTile>
  );
}
