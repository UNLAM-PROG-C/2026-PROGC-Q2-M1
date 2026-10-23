// Paso 2: parámetros del mosaico con ayuda contextual, validación junto a cada
// campo (con las reglas de /api/state) e información del problema en vivo.

import type {Dispatch} from 'react';
import {StepActions} from '../components/StepActions';
import {StepTile} from '../components/StepTile';
import {stepBlocker, type WizardAction, type WizardState} from '../wizard/wizardReducer';
import {ColsControl, OpacityControl, SeedControl, TilePxControl, type ParamChange} from './ParamControls';
import {draftProblemInfo, validateParams} from './params';
import {ProblemInfoPanel} from './ProblemInfoPanel';

interface ParamsStepProps
{
  wizard: WizardState;
  dispatch: Dispatch<WizardAction>;
}

export function ParamsStep({wizard, dispatch}: ParamsStepProps): JSX.Element
{
  const {params, rules} = wizard;
  if (!params || !rules)
  {
    return <StepTile title="Parámetros" tone="parchment" lead="Conectando con el backend…">{null}</StepTile>;
  }
  const errors = validateParams(params, rules, wizard.target);
  const onChange: ParamChange = (patch) => dispatch({type: 'PARAMS_CHANGED', patch});
  const controlProps = {draft: params, rules, errors, onChange};
  return (
    <StepTile title="Parámetros" tone="parchment" lead="Elegí cómo se arma el mosaico.">
      <div className="params-step">
        <ColsControl {...controlProps} />
        <TilePxControl {...controlProps} />
        <OpacityControl {...controlProps} />
        <SeedControl {...controlProps} />
      </div>
      <ProblemInfoPanel info={errors.cols ? null : draftProblemInfo(wizard.tiles, wizard.target, params)} n={wizard.tiles?.accepted ?? 0} />
      {errors.output && <p className="field-error" role="alert">{errors.output}</p>}
      <StepActions primaryLabel="Siguiente" onPrimary={() => dispatch({type: 'NEXT'})} onBack={() => dispatch({type: 'BACK'})} blocker={stepBlocker(wizard)} />
    </StepTile>
  );
}
