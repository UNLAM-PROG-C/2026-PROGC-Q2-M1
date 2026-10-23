// Menú "Descargar": el mosaico en resolución completa en PNG o en JPEG.
// Los enlaces apuntan a los endpoints del backend, que responden con
// `Content-Disposition: attachment` (el atributo `download` no aplica entre orígenes).

import {useState} from 'react';
import {resultUrl} from '../api/client';
import type {BackendName} from '../api/types';
import {PillButton} from '../components/PillButton';

interface DownloadMenuProps
{
  jobId: string;
  backend: BackendName;
}

export function DownloadMenu({jobId, backend}: DownloadMenuProps): JSX.Element
{
  const [open, setOpen] = useState(false);
  return (
    <div className="download-menu">
      <PillButton aria-expanded={open} aria-controls="download-options" onClick={() => setOpen(!open)}>Descargar</PillButton>
      <ul id="download-options" className="download-menu__options" hidden={!open}>
        <li><a className="text-link" href={resultUrl(jobId, backend, 'png')} download="mosaico.png">PNG (sin pérdida)</a></li>
        <li><a className="text-link" href={resultUrl(jobId, backend, 'jpg')} download="mosaico.jpg">JPEG (más liviano)</a></li>
      </ul>
    </div>
  );
}
