import {fireEvent, render, screen} from '@testing-library/react';
import {describe, expect, it, vi} from 'vitest';
import {StepActions} from './StepActions';

const BLOCKER = 'falta la imagen objetivo';
const ERROR = 'el servidor rechazó el trabajo';

describe('StepActions', () =>
{
  it('con un motivo de bloqueo deshabilita la acción principal y lo muestra debajo', () =>
  {
    render(<StepActions primaryLabel="Siguiente" onPrimary={vi.fn()} blocker={BLOCKER} />);
    const next = screen.getByRole('button', {name: 'Siguiente'});
    expect(next).toBeDisabled();
    expect(next).toHaveAccessibleDescription(BLOCKER);
  });

  it('un error se anuncia como alerta y tiene prioridad sobre el bloqueo', () =>
  {
    render(<StepActions primaryLabel="Generar mosaico" onPrimary={vi.fn()} blocker={BLOCKER} error={ERROR} note="nota" />);
    expect(screen.getByRole('alert')).toHaveTextContent(ERROR);
    expect(screen.queryByText(BLOCKER)).not.toBeInTheDocument();
  });

  it('la línea de mensajes existe aunque esté vacía, así los botones no se mueven', () =>
  {
    const {container} = render(<StepActions primaryLabel="Siguiente" onPrimary={vi.fn()} />);
    const message = container.querySelector('.step-actions__message');
    expect(message).toBeInTheDocument();
    expect(message).toBeEmptyDOMElement();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('ordena "Atrás", la acción principal y la secundaria', () =>
  {
    const onBack = vi.fn();
    const onSecondary = vi.fn();
    render(<StepActions primaryLabel="Generar mosaico" onPrimary={vi.fn()} onBack={onBack} secondary={{label: 'Ver resultado', onClick: onSecondary}} />);
    const labels = screen.getAllByRole('button').map((button) => button.textContent);
    expect(labels).toEqual(['Atrás', 'Generar mosaico', 'Ver resultado']);
    fireEvent.click(screen.getByRole('button', {name: 'Atrás'}));
    fireEvent.click(screen.getByRole('button', {name: 'Ver resultado'}));
    expect(onBack).toHaveBeenCalledOnce();
    expect(onSecondary).toHaveBeenCalledOnce();
  });

  it('permite cambiar el texto de "Atrás" (por ejemplo "Cancelar" en una confirmación)', () =>
  {
    render(<StepActions primaryLabel="Generar igual" onPrimary={vi.fn()} onBack={vi.fn()} backLabel="Cancelar" note="puede tardar ~5 min" />);
    expect(screen.getByRole('button', {name: 'Cancelar'})).toBeInTheDocument();
    expect(screen.getByText('puede tardar ~5 min')).toBeInTheDocument();
  });
});
