// Controles del paso 2 con la forma del design system: campos numéricos con
// forma de `search-input`, chips de resolución y slider de opacidad.

import type {ParamRules} from '../api/types';
import {formatInt, PERCENT} from '../common/format';
import type {ParamDraft, ParamErrors} from './params';
import {ParamField} from './ParamField';

export type ParamChange = (patch: Partial<ParamDraft>) => void;

interface ControlProps
{
  draft: ParamDraft;
  rules: ParamRules;
  errors: ParamErrors;
  onChange: ParamChange;
}

export function ColsControl({draft, errors, onChange}: ControlProps): JSX.Element
{
  return (
    <ParamField param="cols" inputId="param-cols" error={errors.cols}>
      {(describedBy) => <input id="param-cols" className="field-input" inputMode="numeric" value={draft.cols} aria-invalid={Boolean(errors.cols)}
        aria-describedby={describedBy} onChange={(event) => onChange({cols: event.target.value})} />}
    </ParamField>
  );
}

export function TilePxControl({draft, rules, onChange}: ControlProps): JSX.Element
{
  const chip = (size: number): JSX.Element => (
    <button key={size} type="button" role="radio" aria-checked={draft.tilePx === size} onClick={() => onChange({tilePx: size})}
      className={draft.tilePx === size ? 'option-chip option-chip--selected' : 'option-chip'}>{size} px</button>
  );
  return (
    <ParamField param="tilePx" inputId="param-tile-px">
      {(describedBy) => <div id="param-tile-px" role="radiogroup" aria-labelledby="param-tile-px-label" aria-describedby={describedBy}
        className="option-chips">{rules.tile_px.allowed.map(chip)}</div>}
    </ParamField>
  );
}

export function OpacityControl({draft, rules, onChange}: ControlProps): JSX.Element
{
  return (
    <ParamField param="opacity" inputId="param-opacity">
      {(describedBy) => (
        <div className="slider-row">
          <input id="param-opacity" type="range" className="slider" min={rules.alpha.min * PERCENT} max={rules.alpha.max * PERCENT} step={1}
            value={draft.opacityPercent} aria-describedby={describedBy} aria-valuetext={`${draft.opacityPercent} %`}
            onChange={(event) => onChange({opacityPercent: Number(event.target.value)})} />
          <output className="slider-row__value" htmlFor="param-opacity">{formatInt(draft.opacityPercent)} %</output>
        </div>
      )}
    </ParamField>
  );
}

export function SeedControl({draft, errors, onChange}: ControlProps): JSX.Element
{
  return (
    <ParamField param="seed" inputId="param-seed" error={errors.seed}>
      {(describedBy) => <input id="param-seed" className="field-input" inputMode="numeric" value={draft.seed} aria-invalid={Boolean(errors.seed)}
        aria-describedby={describedBy} onChange={(event) => onChange({seed: event.target.value})} />}
    </ParamField>
  );
}
