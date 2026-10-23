// Tabla de tiempos de un backend, con números tabulares (design D12).

import type {BackendResult, LoadInfo} from '../api/types';
import {timingRows} from './timings';

interface TimingsTableProps
{
  load: LoadInfo | null;
  result: BackendResult;
  caption: string;
}

export function TimingsTable({load, result, caption}: TimingsTableProps): JSX.Element
{
  return (
    <table className="timings-table">
      <caption className="timings-table__caption">{caption}</caption>
      <thead>
        <tr>
          <th scope="col">Etapa</th>
          <th scope="col">Tiempo</th>
        </tr>
      </thead>
      <tbody>
        {timingRows(load, result).map((row) => (
          <tr key={row.label}>
            <th scope="row">{row.label}</th>
            <td>{row.value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
