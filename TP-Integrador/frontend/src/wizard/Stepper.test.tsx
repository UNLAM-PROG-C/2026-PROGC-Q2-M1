import {fireEvent, render, screen} from '@testing-library/react';
import {describe, expect, it, vi} from 'vitest';
import {Stepper} from './Stepper';

describe('Stepper', () =>
{
  it('marca el paso actual y permite volver solo a los completos', () =>
  {
    const dispatch = vi.fn();
    render(<Stepper phase="params" dispatch={dispatch} />);
    expect(screen.getByText('2. Parámetros')).toHaveAttribute('aria-current', 'step');
    expect(screen.queryByRole('button', {name: '3. Ejecución'})).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: '1. Imágenes'}));
    expect(dispatch).toHaveBeenCalledWith({type: 'GO_TO', phase: 'images'});
  });

  it('incluye la versión compacta "Paso N de 3 · Nombre" y es la única navegación', () =>
  {
    render(<Stepper phase="params" dispatch={vi.fn()} />);
    expect(screen.getByText('Paso 2 de 3 · Parámetros')).toBeInTheDocument();
    expect(screen.getAllByRole('navigation')).toHaveLength(1);
  });
});
