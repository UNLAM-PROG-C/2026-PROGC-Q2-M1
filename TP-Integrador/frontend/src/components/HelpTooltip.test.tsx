import {fireEvent, render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, expect, it} from 'vitest';
import {HelpTooltip} from './HelpTooltip';

const HELP_TEXT = 'Texto de ayuda de prueba';

function renderTooltip(): HTMLElement
{
  render(
    <>
      <input aria-describedby="help-test" aria-label="Campo" />
      <HelpTooltip id="help-test" text={HELP_TEXT} label="Ayuda: Campo" />
    </>,
  );
  return screen.getByRole('button', {name: 'Ayuda: Campo'});
}

describe('HelpTooltip', () =>
{
  it('empieza oculto', () =>
  {
    renderTooltip();
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('se muestra con mouseenter y se oculta con mouseleave', async () =>
  {
    const user = userEvent.setup();
    const button = renderTooltip();
    await user.hover(button);
    expect(screen.getByRole('tooltip')).toHaveTextContent(HELP_TEXT);
    await user.unhover(button);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('se muestra con focus y se oculta con Escape', () =>
  {
    const button = renderTooltip();
    fireEvent.focus(button);
    expect(screen.getByRole('tooltip')).toBeVisible();
    fireEvent.keyDown(button, {key: 'Escape'});
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('se muestra al llegar con Tab y se oculta al salir', async () =>
  {
    const user = userEvent.setup();
    renderTooltip();
    await user.tab();
    await user.tab();
    expect(screen.getByRole('tooltip')).toBeVisible();
    await user.tab();
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('queda vinculado por aria-describedby al campo y al botón', () =>
  {
    const button = renderTooltip();
    expect(screen.getByRole('textbox', {name: 'Campo'})).toHaveAccessibleDescription(HELP_TEXT);
    expect(button).toHaveAccessibleDescription(HELP_TEXT);
  });
});
