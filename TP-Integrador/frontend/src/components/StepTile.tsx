// Contenedor de cada paso (`product-tile-light` / `product-tile-parchment`):
// título display-lg, bajada lead y el contenido centrado a 980 px.

import type {ReactNode} from 'react';

export type TileTone = 'light' | 'parchment' | 'dark';

interface StepTileProps
{
  title: string;
  lead?: string;
  tone?: TileTone;
  children: ReactNode;
}

export function StepTile({title, lead, tone = 'light', children}: StepTileProps): JSX.Element
{
  return (
    <section className={`step-tile step-tile--${tone}`} aria-label={title}>
      <div className="step-tile__inner">
        <h2 className="step-tile__title">{title}</h2>
        {lead && <p className="step-tile__lead">{lead}</p>}
        {children}
      </div>
    </section>
  );
}
