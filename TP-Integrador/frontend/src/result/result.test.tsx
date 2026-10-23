import {fireEvent, render, screen} from '@testing-library/react';
import {describe, expect, it, vi} from 'vitest';
import {stageFractions} from '../run/stages';
import {makeCpuResult, makeJob} from '../testing/fixtures';
import {tilesSummaryText} from '../steps/imagesText';
import {ResultView} from './ResultView';
import {NOT_APPLICABLE, timingRows} from './timings';
import {FIT_VIEW, MAX_ZOOM, needsFullImage, zoomAt} from './zoom';

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

  it('no se muestran hasta apretar "Ver estadísticas"', () =>
  {
    render(<ResultView job={makeJob({status: 'finished', load: LOAD, results: [CPU_RESULT]})} onRestart={vi.fn()} />);
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: 'Ver estadísticas'}));
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('un trabajo fallido muestra el motivo y "Volver a empezar"', () =>
  {
    const onRestart = vi.fn();
    render(<ResultView job={makeJob({status: 'failed', error: 'memoria insuficiente en el dispositivo'})} onRestart={onRestart} />);
    expect(screen.getByRole('alert')).toHaveTextContent('memoria insuficiente en el dispositivo');
    fireEvent.click(screen.getByRole('button', {name: 'Volver a empezar'}));
    expect(onRestart).toHaveBeenCalled();
  });

  it('si otra pestaña lanzó un trabajo nuevo, el resultado viejo ofrece "Volver a empezar"', () =>
  {
    const onRestart = vi.fn();
    render(<ResultView job={null} onRestart={onRestart} />);
    expect(screen.getByRole('alert')).toHaveTextContent('ya no está disponible');
    fireEvent.click(screen.getByRole('button', {name: 'Volver a empezar'}));
    expect(onRestart).toHaveBeenCalled();
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

  it('un mosaico gigante no carga el PNG completo (escenario "Mosaico grande")', () =>
  {
    expect(needsFullImage(8, 1000, 2048, 12_800 * 9_600)).toBe(false);
    expect(needsFullImage(8, 1000, 2048, 3200 * 2400)).toBe(true);
    expect(needsFullImage(1, 1000, 2048, 3200 * 2400)).toBe(false);
  });

  it('resume el lote como "200 teselas · 3 archivos ignorados"', () =>
  {
    expect(tilesSummaryText({tiles_id: 't', accepted: 200, ignored: 3, rejected: 0, samples: []})).toBe('200 teselas · 3 archivos ignorados');
  });
});
