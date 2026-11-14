// Plantilla de pantalla de cada paso (design D1 del cambio
// consistencia-visual-del-stepper): encabezado (título igual al del stepper y
// bajada con la instrucción o el estado), contenido centrado a 980 px y la
// barra de acciones fija abajo. Es un Template Method por composición: el
// esqueleto es siempre el mismo y cada fase solo completa las ranuras, así
// ningún paso puede mover el título ni los botones de lugar.
// El tono sigue el tipo de paso: light donde se completa algo, parchment donde
// el sistema informa y dark solo para el resultado. Con `fit` el tile mide el
// alto de la ventana y el contenido toma el espacio libre (el visor del mosaico).

import type {ReactNode} from 'react';

export type TileTone = 'light' | 'parchment' | 'dark';

interface StepTileProps
{
  title: string;
  lead?: string;
  tone?: TileTone;
  fit?: boolean;
  /** Contenido de la barra fija: normalmente `StepActions`. */
  actions?: ReactNode;
  children?: ReactNode;
}

function tileClasses(tone: TileTone, fit: boolean): string
{
  return `step-tile step-tile--${tone}${fit ? ' step-tile--fit' : ''}`;
}

export function StepTile({title, lead, tone = 'light', fit = false, actions, children}: StepTileProps): JSX.Element
{
  return (
    <section className={tileClasses(tone, fit)} aria-label={title}>
      <div className="step-tile__inner">
        <header className="step-tile__header">
          <h2 className="step-tile__title">{title}</h2>
          {lead && <p className="step-tile__lead">{lead}</p>}
        </header>
        {children}
      </div>
      <footer className="step-bar" role="group" aria-label="Acciones del paso">
        <div className="step-bar__inner">{actions}</div>
      </footer>
    </section>
  );
}
