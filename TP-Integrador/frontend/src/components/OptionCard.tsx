// Tarjeta seleccionable (`store-utility-card` con el borde de selección de
// `configurator-option-chip-selected`). Se comporta como un radio button.

import type {ReactNode} from 'react';

interface OptionCardProps
{
  title: string;
  selected: boolean;
  disabled?: boolean;
  /** Texto secundario: detalle de la opción o motivo por el que está deshabilitada. */
  detail?: ReactNode;
  onSelect: () => void;
}

export function OptionCard({title, selected, disabled = false, detail, onSelect}: OptionCardProps): JSX.Element
{
  const classes = ['option-card', selected ? 'option-card--selected' : '', disabled ? 'option-card--disabled' : ''].join(' ').trim();
  return (
    <button type="button" role="radio" aria-checked={selected} disabled={disabled} className={classes} onClick={onSelect}>
      <span className="option-card__title">{title}</span>
      {detail && <span className="option-card__detail">{detail}</span>}
    </button>
  );
}
