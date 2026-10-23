// Tabla de tiempos con números tabulares (design D12): una columna por backend
// y, en una comparación, una de speedup (cambio 4).

import type {TableRow} from './timings';

interface TimingsTableProps
{
  caption: string;
  columns: readonly string[];
  rows: readonly TableRow[];
}

export function TimingsTable({caption, columns, rows}: TimingsTableProps): JSX.Element
{
  return (
    <table className="timings-table">
      <caption className="timings-table__caption">{caption}</caption>
      <thead>
        <tr>
          <th scope="col">Etapa</th>
          {columns.map((column) => <th key={column} scope="col">{column}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.label}>
            <th scope="row">{row.label}</th>
            {row.values.map((value, index) => <td key={columns[index]}>{value}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
