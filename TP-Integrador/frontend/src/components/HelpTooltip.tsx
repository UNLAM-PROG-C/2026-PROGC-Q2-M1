// Ayuda contextual "?" (design D9): se muestra con mouseenter/focus, se oculta
// con mouseleave/blur/Escape y en pantallas táctiles un toque la alterna.
// El texto vive en un elemento role="tooltip" que siempre está en el DOM
// (oculto cuando no se muestra) para que `aria-describedby` lo resuelva.

import {useRef, useState, type KeyboardEvent, type PointerEvent} from 'react';

interface HelpTooltipProps
{
  /** Id del elemento del texto; el campo lo referencia con `aria-describedby`. */
  id: string;
  text: string;
  /** Nombre accesible del botón, por ejemplo "Ayuda: Semilla". */
  label: string;
}

export function HelpTooltip({id, text, label}: HelpTooltipProps): JSX.Element
{
  const [open, setOpen] = useState(false);
  // Estado deseado tras un toque: se calcula antes de que el foco o el mouse emulado lo cambien.
  const touchTarget = useRef<boolean | null>(null);

  const onPointerDown = (event: PointerEvent): void =>
  {
    touchTarget.current = event.pointerType === 'touch' ? !open : null;
  };
  const onClick = (): void =>
  {
    if (touchTarget.current !== null)
    {
      setOpen(touchTarget.current);
      touchTarget.current = null;
    }
  };
  const onKeyDown = (event: KeyboardEvent): void => setOpen((current) => current && event.key !== 'Escape');

  return (
    <span className="help-tooltip" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" className="help-tooltip__button" aria-label={label} aria-describedby={id}
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} onKeyDown={onKeyDown} onPointerDown={onPointerDown} onClick={onClick}>
        <span className="help-tooltip__icon" aria-hidden="true">?</span>
      </button>
      <span id={id} role="tooltip" className="help-tooltip__text" hidden={!open}>{text}</span>
    </span>
  );
}
