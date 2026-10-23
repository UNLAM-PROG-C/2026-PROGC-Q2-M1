import {fireEvent, render, screen} from '@testing-library/react';
import {useReducer} from 'react';
import {describe, expect, it} from 'vitest';
import {makeRules, makeWizard} from '../testing/fixtures';
import {wizardReducer, type WizardState} from '../wizard/wizardReducer';
import {buildJobRequest} from './execution';
import {PARAM_HELP} from './paramHelp';
import {draftProblemInfo, opacityToAlpha, validateParams} from './params';
import {ParamsStep} from './ParamsStep';

function Harness({initial}: {initial: WizardState}): JSX.Element
{
  const [wizard, dispatch] = useReducer(wizardReducer, initial);
  return <ParamsStep wizard={wizard} dispatch={dispatch} />;
}

function renderParams(overrides: Partial<WizardState> = {}): void
{
  render(<Harness initial={makeWizard({phase: 'params', ...overrides})} />);
}

describe('ParamsStep: ayuda contextual', () =>
{
  it('cada parámetro tiene su "?" con el texto de la spec vinculado al campo', () =>
  {
    renderParams();
    for (const {label, help} of Object.values(PARAM_HELP))
    {
      expect(screen.getByRole('button', {name: `Ayuda: ${label}`})).toHaveAccessibleDescription(help);
    }
    expect(screen.getByLabelText('Columnas de la grilla')).toHaveAccessibleDescription(PARAM_HELP.cols.help);
    expect(screen.getByLabelText('Semilla')).toHaveAccessibleDescription(PARAM_HELP.seed.help);
  });

  it('usa los textos exactos de la spec', () =>
  {
    expect(PARAM_HELP.cols.help).toBe('Cantidad de teselas a lo ancho del mosaico. Más columnas dan más detalle, pero el mosaico tarda más y la imagen final es más grande. ' +
      'Las filas se calculan solas según la proporción de la imagen objetivo.');
    expect(PARAM_HELP.tilePx.help).toBe('Tamaño en píxeles con el que se dibuja cada tesela en el mosaico final. Más resolución da una imagen más nítida al hacer zoom, pero más pesada.');
    expect(PARAM_HELP.opacity.help).toBe('Cuánto se ve la foto de cada tesela. Con 100 % se ven las fotos tal cual; con valores menores, cada tesela se tiñe con el color de ' +
      'esa zona de la imagen objetivo y el mosaico se parece más a ella.');
    expect(PARAM_HELP.seed.help).toBe('Número que fija las elecciones al azar entre teselas parecidas. Con la misma semilla y los mismos parámetros se obtiene exactamente el ' +
      'mismo mosaico; cambiala para ver otra variante.');
  });
});

describe('ParamsStep: opacidad', () =>
{
  it('60 % se envía como alpha = 0.6', () =>
  {
    expect(opacityToAlpha(60)).toBeCloseTo(0.6);
    const wizard = makeWizard({phase: 'execution', params: {cols: '100', tilePx: 32, opacityPercent: 60, seed: '0'}});
    expect(buildJobRequest(wizard)?.alpha).toBeCloseTo(0.6);
  });

  it('el slider muestra el porcentaje elegido', () =>
  {
    renderParams();
    fireEvent.change(screen.getByLabelText('Opacidad de las teselas'), {target: {value: '60'}});
    expect(screen.getByText('60 %')).toBeInTheDocument();
  });
});

describe('ParamsStep: validación', () =>
{
  it('columnas fuera de rango marcan el campo con el rango y bloquean "Siguiente"', () =>
  {
    renderParams();
    const cols = screen.getByLabelText('Columnas de la grilla');
    fireEvent.change(cols, {target: {value: '401'}});
    expect(cols).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getAllByText(/entre 1 y 400/).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', {name: 'Siguiente'})).toBeDisabled();
  });

  it('con valores válidos "Siguiente" está habilitado', () =>
  {
    renderParams();
    expect(screen.getByRole('button', {name: 'Siguiente'})).toBeEnabled();
  });

  it('una salida mayor al límite advierte y bloquea (escenario "Salida gigante")', () =>
  {
    const rules = makeRules({max_output_pixels: 1_000_000});
    const wizard = makeWizard({phase: 'params', rules});
    expect(validateParams(wizard.params!, rules, wizard.target).output).toMatch(/supera el límite/);
    renderParams({rules});
    expect(screen.getByRole('button', {name: 'Siguiente'})).toBeDisabled();
  });
});

describe('ParamsStep: información del problema (escenario "Cambio de columnas")', () =>
{
  it('con N = 1.000 y objetivo 4:3, pasar de 100 a 200 columnas lleva M de 7.500 a 30.000', () =>
  {
    const wizard = makeWizard();
    const before = draftProblemInfo(wizard.tiles, wizard.target, {...wizard.params!, cols: '100'});
    const after = draftProblemInfo(wizard.tiles, wizard.target, {...wizard.params!, cols: '200'});
    expect(before).toMatchObject({m: 7500, pairs: 7_500_000});
    expect(after).toMatchObject({m: 30000, pairs: 30_000_000});
  });

  it('se recalcula en vivo al cambiar las columnas', () =>
  {
    renderParams();
    expect(screen.getByText('7,5 millones')).toBeInTheDocument();
    expect(screen.getByText(/^7\.500 /)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Columnas de la grilla'), {target: {value: '200'}});
    expect(screen.getByText('30 millones')).toBeInTheDocument();
    expect(screen.getByText(/^30\.000 /)).toBeInTheDocument();
  });
});
