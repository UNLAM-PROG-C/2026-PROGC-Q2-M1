import {describe, expect, it} from 'vitest';
import {buildTilesForm, errorMessage, resultUrl} from './client';
import {reconnectDelayMs} from './socket';

function file(name: string): File
{
  return new File(['x'], name);
}

describe('client', () =>
{
  it('un único zip viaja en el campo `zip`', () =>
  {
    const form = buildTilesForm([file('lote.ZIP')]);
    expect(form.getAll('zip')).toHaveLength(1);
    expect(form.getAll('files')).toHaveLength(0);
  });

  it('varios archivos viajan repetidos en el campo `files`', () =>
  {
    const form = buildTilesForm([file('a.jpg'), file('b.png')]);
    expect(form.getAll('files')).toHaveLength(2);
  });

  it('toma el motivo del `detail` de FastAPI', () =>
  {
    expect(errorMessage({detail: 'ya hay un trabajo en curso'}, 409)).toBe('ya hay un trabajo en curso');
    expect(errorMessage({detail: [{msg: 'cols fuera de rango'}]}, 422)).toBe('cols fuera de rango');
    expect(errorMessage(null, 500)).toBe('error del servidor (500)');
  });

  it('arma las URLs de resultados por backend y formato', () =>
  {
    expect(resultUrl('job-1', 'cuda', 'jpg')).toMatch(/\/api\/jobs\/job-1\/cuda\/jpg$/);
  });

  it('la espera de reconexión crece y queda acotada', () =>
  {
    expect(reconnectDelayMs(0)).toBeLessThan(reconnectDelayMs(1));
    expect(reconnectDelayMs(100)).toBe(reconnectDelayMs(101));
  });
});
