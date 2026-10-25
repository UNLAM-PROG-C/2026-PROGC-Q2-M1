import {render, screen} from '@testing-library/react';
import {describe, expect, it} from 'vitest';
import {StepTile} from './StepTile';

function follows(first: HTMLElement, second: HTMLElement): boolean
{
  return (first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
}

describe('StepTile', () =>
{
  it('ubica título, bajada, contenido y acciones en ese orden', () =>
  {
    render(
      <StepTile title="Ejecución" lead="Elegí dónde se calcula el mosaico." actions={<button type="button">Generar mosaico</button>}>
        <p>Contenido del paso</p>
      </StepTile>,
    );
    const title = screen.getByRole('heading', {name: 'Ejecución'});
    const lead = screen.getByText('Elegí dónde se calcula el mosaico.');
    const content = screen.getByText('Contenido del paso');
    const action = screen.getByRole('button', {name: 'Generar mosaico'});
    expect(follows(title, lead) && follows(lead, content) && follows(content, action)).toBe(true);
    expect(screen.getByRole('group', {name: 'Acciones del paso'})).toContainElement(action);
  });

  it('la barra de acciones existe aunque el paso no tenga acciones', () =>
  {
    render(<StepTile title="Generando">{null}</StepTile>);
    expect(screen.getByRole('group', {name: 'Acciones del paso'})).toBeInTheDocument();
  });

  it('aplica el tono y el modo a alto de ventana', () =>
  {
    render(<StepTile title="Resultado" tone="dark" fit>{null}</StepTile>);
    expect(screen.getByRole('region', {name: 'Resultado'})).toHaveClass('step-tile--dark', 'step-tile--fit');
  });
});
