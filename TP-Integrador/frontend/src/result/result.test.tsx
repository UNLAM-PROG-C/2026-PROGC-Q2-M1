import {fireEvent, render, screen, within} from '@testing-library/react';
import {describe, expect, it, vi} from 'vitest';
import {stageFractions} from '../run/stages';
import {makeCpuResult, makeJob} from '../testing/fixtures';
import {tilesSummaryText} from '../steps/imagesText';
import {ResultView} from './ResultView';
import {StatsPanel} from './StatsPanel';
import {NOT_APPLICABLE, timingRows} from './timings';
import {composeViews, FIT_VIEW, fitView, FULL_IMAGE_MAX_PIXELS, MAX_ZOOM, needsFullImage, showsRealPixels, zoomAt} from './zoom';

const CPU_RESULT = makeCpuResult();
const LOAD = {load_ms: 12, reused: true, n_tiles: 200, skipped_files: 0, rows: 75, cols: 100, m_cells: 7500};

describe('estadísticas', () =>
{
  it('en CPU las transferencias dicen "no aplica" y el resto tiene ms', () =>
  {
    const rows = timingRows(LOAD, CPU_RESULT);
    const transfers = rows.filter((row) => row.label.startsWith('Transferencia'));
    expect(transfers).toHaveLength(4);
    transfers.forEach((row) => expect(row.value).toBe(NOT_APPLICABLE));
    rows.filter((row) => !row.label.startsWith('Transferencia')).forEach((row) => expect(row.value).toMatch(/ms/));
  });

  it('indica cuando la carga común se reutilizó', () =>
  {
    expect(timingRows(LOAD, CPU_RESULT)[0].value).toMatch(/reutilizada/);
  });

  it('el resultado no muestra tablas y "Ver estadísticas" avanza al paso 5 (escenario "Resultado sin estadísticas")', () =>
  {
    const dispatch = vi.fn();
    render(<ResultView job={makeJob({status: 'finished', load: LOAD, results: [CPU_RESULT]})} dispatch={dispatch} />);
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: 'Ver estadísticas'}));
    expect(dispatch).toHaveBeenCalledWith({type: 'NEXT'});
  });

  it('el título es "Resultado" y la bajada indica backend, dispositivo y tamaño (escenario "Título del resultado")', () =>
  {
    render(<ResultView job={makeJob({status: 'finished', load: LOAD, results: [CPU_RESULT]})} dispatch={vi.fn()} />);
    expect(screen.getByRole('heading', {name: 'Resultado'})).toBeInTheDocument();
    expect(screen.getByText(/^CPU \(CPU de prueba\) · .* px$/)).toBeInTheDocument();
    expect(screen.getByRole('region', {name: 'Resultado'})).toHaveClass('step-tile--dark');
  });

  it('"Ver estadísticas" es el único botón principal y "Descargar" es secundario junto al zoom', () =>
  {
    const {container} = render(<ResultView job={makeJob({status: 'finished', load: LOAD, results: [CPU_RESULT]})} dispatch={vi.fn()} />);
    const primaries = Array.from(container.querySelectorAll('.pill-button--primary')).map((button) => button.textContent);
    expect(primaries).toEqual(['Ver estadísticas']);
    const download = screen.getByRole('button', {name: 'Descargar'});
    expect(download).toHaveClass('pill-button--secondary');
    expect(screen.getByLabelText('Controles del mosaico')).toContainElement(download);
  });

  it('el menú de descarga muestra PNG y JPEG al abrirlo', () =>
  {
    render(<ResultView job={makeJob({status: 'finished', load: LOAD, results: [CPU_RESULT]})} dispatch={vi.fn()} />);
    expect(screen.getByText('PNG (sin pérdida)')).not.toBeVisible();
    fireEvent.click(screen.getByRole('button', {name: 'Descargar'}));
    expect(screen.getByText('PNG (sin pérdida)')).toBeVisible();
    expect(screen.getByText('JPEG (más liviano)')).toBeVisible();
  });

  it('el resultado ofrece "Atrás" hacia la ejecución y "Volver a empezar"', () =>
  {
    const dispatch = vi.fn();
    render(<ResultView job={makeJob({status: 'finished', load: LOAD, results: [CPU_RESULT]})} dispatch={dispatch} />);
    fireEvent.click(screen.getByRole('button', {name: 'Atrás'}));
    fireEvent.click(screen.getByRole('button', {name: 'Volver a empezar'}));
    expect(dispatch.mock.calls).toEqual([[{type: 'BACK'}], [{type: 'RESTART'}]]);
  });

  it('el paso 5 muestra la tabla de tiempos de CPU, "Atrás" y "Volver a empezar" (escenario "Trabajo en CPU")', () =>
  {
    const dispatch = vi.fn();
    render(<StatsPanel job={makeJob({status: 'finished', load: LOAD, results: [CPU_RESULT]})} dispatch={dispatch} />);
    expect(screen.getByRole('table', {name: /CPU/})).toHaveTextContent(NOT_APPLICABLE);
    fireEvent.click(screen.getByRole('button', {name: 'Atrás'}));
    fireEvent.click(screen.getByRole('button', {name: 'Volver a empezar'}));
    expect(dispatch.mock.calls).toEqual([[{type: 'BACK'}], [{type: 'RESTART'}]]);
  });

  it('un trabajo fallido es el mismo paso oscuro con el motivo en la barra y "Volver a empezar" (escenario "Fallo dentro del paso Resultado")', () =>
  {
    const dispatch = vi.fn();
    render(<ResultView job={makeJob({status: 'failed', error: 'memoria insuficiente en el dispositivo'})} dispatch={dispatch} />);
    expect(within(screen.getByRole('group', {name: 'Acciones del paso'})).getByRole('alert')).toHaveTextContent('memoria insuficiente en el dispositivo');
    expect(screen.getByRole('heading', {name: 'Resultado'})).toBeInTheDocument();
    expect(screen.getByRole('region', {name: 'Resultado'})).toHaveClass('step-tile--dark');
    expect(screen.queryByRole('button', {name: 'Ver estadísticas'})).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: 'Volver a empezar'}));
    expect(dispatch).toHaveBeenCalledWith({type: 'RESTART'});
  });

  it('si otra pestaña lanzó un trabajo nuevo, el resultado y las estadísticas viejas ofrecen "Volver a empezar"', () =>
  {
    const dispatch = vi.fn();
    const {unmount} = render(<ResultView job={null} dispatch={dispatch} />);
    expect(screen.getByRole('alert')).toHaveTextContent('ya no está disponible');
    unmount();
    render(<StatsPanel job={null} dispatch={dispatch} />);
    expect(screen.getByRole('heading', {name: 'Estadísticas'})).toBeInTheDocument();
    expect(within(screen.getByRole('group', {name: 'Acciones del paso'})).getByRole('alert')).toHaveTextContent('ya no está disponible');
    fireEvent.click(screen.getByRole('button', {name: 'Volver a empezar'}));
    expect(dispatch).toHaveBeenCalledWith({type: 'RESTART'});
  });
});

describe('progreso y visor', () =>
{
  it('las etapas anteriores a la actual quedan completas', () =>
  {
    const fractions = stageFractions({backend: 'cpu', stage: 'matching', fraction: 0.4});
    expect(fractions).toMatchObject({load: 1, prepare_tiles: 1, target_descriptors: 1, matching: 0.4, compose: 0, save: 0});
  });

  it('el zoom deja fijo el punto bajo el cursor y se acota', () =>
  {
    const zoomed = zoomAt(FIT_VIEW, 2, {x: 100, y: 50});
    expect(zoomed).toEqual({scale: 2, x: -100, y: -50});
    expect(zoomAt(zoomed, 1000, {x: 0, y: 0}).scale).toBe(MAX_ZOOM);
    expect(zoomAt(zoomed, 0.01, {x: 0, y: 0})).toEqual(FIT_VIEW);
  });

  it('un mosaico grande arranca con la vista previa y al acercar carga el completo (escenario "Mosaico grande")', () =>
  {
    expect(needsFullImage(1, 1000, 2048, 12_800 * 9_600)).toBe(false);
    expect(needsFullImage(8, 1000, 2048, 12_800 * 9_600)).toBe(true);
    expect(needsFullImage(8, 1000, 2048, 3200 * 2400)).toBe(true);
    expect(needsFullImage(1, 1000, 2048, 3200 * 2400)).toBe(false);
  });

  it('por encima del límite configurado se queda con la vista previa', () =>
  {
    expect(needsFullImage(8, 1000, 2048, FULL_IMAGE_MAX_PIXELS + 1)).toBe(false);
  });

  it('en Retina la vista previa se queda corta sin zoom: el ancho va en píxeles físicos', () =>
  {
    const retinaFit = 3200 * fitView(1200, 600, 3200, 2400).scale * 2;
    expect(retinaFit).toBe(1600);
    expect(needsFullImage(1.5, retinaFit, 2048, 3200 * 2400)).toBe(true);
    expect(needsFullImage(1.5, retinaFit / 2, 2048, 3200 * 2400)).toBe(false);
  });

  it('encaja el mosaico completo centrado en el visor, como object-fit: contain', () =>
  {
    expect(fitView(1200, 600, 3200, 2400)).toEqual({scale: 0.25, x: 200, y: 0});
  });

  it('el zoom se aplica sobre el encaje: el punto bajo el cursor queda fijo', () =>
  {
    const fit = fitView(1200, 600, 3200, 2400);
    const shown = composeViews(zoomAt(FIT_VIEW, 2, {x: 600, y: 300}), fit);
    expect(shown.scale).toBe(0.5);
    // El centro del mosaico (1600, 1200) sigue en el centro del visor.
    expect({x: shown.x + 1600 * shown.scale, y: shown.y + 1200 * shown.scale}).toEqual({x: 600, y: 300});
  });

  it('se dibuja sin suavizar solo pasado 1:1 con la imagen completa', () =>
  {
    expect(showsRealPixels(1, 1600, 3200)).toBe(false);
    expect(showsRealPixels(3, 1600, 3200)).toBe(true);
  });

  it('resume el lote como "200 teselas · 3 archivos ignorados"', () =>
  {
    expect(tilesSummaryText({tiles_id: 't', accepted: 200, ignored: 3, rejected: 0, samples: []})).toBe('200 teselas · 3 archivos ignorados');
  });
});
