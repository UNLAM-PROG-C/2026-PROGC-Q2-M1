import {fireEvent, render, screen} from '@testing-library/react';
import {describe, expect, it, vi} from 'vitest';
import {makeWizard} from '../testing/fixtures';
import {Stepper} from './Stepper';

describe('Stepper', () =>
{
  it('marca el paso actual y permite volver a los anteriores', () =>
  {
    const dispatch = vi.fn();
    render(<Stepper wizard={makeWizard({phase: 'params'})} dispatch={dispatch} />);
    expect(screen.getByText('2. Parámetros')).toHaveAttribute('aria-current', 'step');
    fireEvent.click(screen.getByRole('button', {name: '1. Imágenes'}));
    expect(dispatch).toHaveBeenCalledWith({type: 'GO_TO', phase: 'images'});
  });

  it('sin resultado los pasos 4 y 5 no son links (escenario "Sin resultado")', () =>
  {
    render(<Stepper wizard={makeWizard({phase: 'params'})} dispatch={vi.fn()} />);
    expect(screen.queryByRole('button', {name: '4. Resultado'})).not.toBeInTheDocument();
    expect(screen.queryByRole('button', {name: '5. Estadísticas'})).not.toBeInTheDocument();
  });

  it('con un resultado ofrece links hacia adelante (escenario "Salto hacia adelante desde el stepper")', () =>
  {
    const dispatch = vi.fn();
    render(<Stepper wizard={makeWizard({jobId: 'job-1', resultReady: true})} dispatch={dispatch} />);
    fireEvent.click(screen.getByRole('button', {name: '5. Estadísticas'}));
    expect(dispatch).toHaveBeenCalledWith({type: 'GO_TO', phase: 'stats'});
    expect(screen.getByRole('button', {name: '4. Resultado'})).toBeInTheDocument();
  });

  it('mientras se genera muestra "4. Generando" como actual y no ofrece links', () =>
  {
    render(<Stepper wizard={makeWizard({phase: 'running', jobId: 'job-1'})} dispatch={vi.fn()} />);
    expect(screen.getByText('4. Generando')).toHaveAttribute('aria-current', 'step');
    expect(screen.queryAllByRole('button')).toHaveLength(0);
    expect(screen.getByText('Paso 4 de 5 · Generando')).toBeInTheDocument();
  });

  it('incluye la versión compacta "Paso N de 5 · Nombre" y es la única navegación', () =>
  {
    render(<Stepper wizard={makeWizard({phase: 'params'})} dispatch={vi.fn()} />);
    expect(screen.getByText('Paso 2 de 5 · Parámetros')).toBeInTheDocument();
    expect(screen.getAllByRole('navigation')).toHaveLength(1);
  });
});
