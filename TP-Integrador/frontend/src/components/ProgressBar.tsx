// Barra de progreso: tramo {colors.primary} sobre riel {colors.hairline}.

import {PERCENT} from '../common/format';

interface ProgressBarProps
{
  label: string;
  fraction: number;
}

export function ProgressBar({label, fraction}: ProgressBarProps): JSX.Element
{
  const percent = Math.round(Math.min(1, Math.max(0, fraction)) * PERCENT);
  return (
    <div className="progress-bar" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={PERCENT} aria-valuenow={percent}>
      <div className="progress-bar__fill" style={{width: `${percent}%`}} />
    </div>
  );
}
