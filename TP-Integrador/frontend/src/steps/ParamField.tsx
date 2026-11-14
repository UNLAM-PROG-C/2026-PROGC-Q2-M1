// Campo del paso 2: etiqueta con su ayuda "?", el control y el error debajo.
// El control recibe en `describedBy` los ids de la ayuda y del error para
// ponerlos en `aria-describedby` (spec "Ayuda contextual de los parámetros").

import type {ReactNode} from 'react';
import {HelpTooltip} from '../components/HelpTooltip';
import {PARAM_HELP, type ParamKey} from './paramHelp';

interface ParamFieldProps
{
  param: ParamKey;
  inputId: string;
  error?: string;
  children: (describedBy: string) => ReactNode;
}

export function ParamField({param, inputId, error, children}: ParamFieldProps): JSX.Element
{
  const {label, help} = PARAM_HELP[param];
  const helpId = `${inputId}-help`;
  const errorId = `${inputId}-error`;
  return (
    <div className="param-field">
      <div className="param-field__label-row">
        <label className="param-field__label" htmlFor={inputId} id={`${inputId}-label`}>{label}</label>
        <HelpTooltip id={helpId} text={help} label={`Ayuda: ${label}`} />
      </div>
      {children(error ? `${helpId} ${errorId}` : helpId)}
      {error && <p id={errorId} className="field-error" role="alert">{error}</p>}
    </div>
  );
}
