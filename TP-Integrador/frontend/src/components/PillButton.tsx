// Botones del design system: `button-primary` (píldora Action Blue) y
// `button-secondary-pill` (píldora transparente con borde azul).

import type {ButtonHTMLAttributes} from 'react';

type PillVariant = 'primary' | 'secondary';

interface PillButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>
{
  variant?: PillVariant;
}

export function PillButton({variant = 'primary', className = '', type = 'button', ...rest}: PillButtonProps): JSX.Element
{
  return <button type={type} className={`pill-button pill-button--${variant} ${className}`.trim()} {...rest} />;
}
