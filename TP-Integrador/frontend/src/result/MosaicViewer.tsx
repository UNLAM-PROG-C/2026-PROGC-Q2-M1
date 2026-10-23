// Visor del mosaico: muestra la vista previa reducida y permite acercar con la
// rueda (o los botones) y arrastrar. Pasado cierto zoom, si el mosaico no es
// gigante, carga el PNG completo en segundo plano y lo reemplaza al terminar
// (spec "Resultado con zoom"). Con `zoom` comparte la vista con otro visor
// (comparación del cambio 4); sin él usa un controlador propio.

import {useEffect, useRef, useState} from 'react';
import {needsFullImage, ZOOM_STEP} from './zoom';
import {ZoomController} from './zoomController';
import {useZoomPan} from './useZoomPan';

interface MosaicViewerProps
{
  previewUrl: string;
  fullUrl: string;
  width: number;
  height: number;
  alt: string;
  zoom?: ZoomController;
}

/** Cambia a la imagen completa cuando el zoom lo pide; la precarga para no mostrar un hueco. */
function useProgressiveSource(previewUrl: string, fullUrl: string, wantFull: boolean): string
{
  const [source, setSource] = useState(previewUrl);
  useEffect(() =>
  {
    if (!wantFull || source === fullUrl)
    {
      return;
    }
    const loader = new Image();
    loader.onload = () => setSource(fullUrl);
    loader.src = fullUrl;
  }, [wantFull, fullUrl, source]);
  return source;
}

export function MosaicViewer({previewUrl, fullUrl, width, height, alt, zoom}: MosaicViewerProps): JSX.Element
{
  const container = useRef<HTMLDivElement>(null);
  const image = useRef<HTMLImageElement>(null);
  const [ownZoom] = useState(() => new ZoomController());
  const {view, zoomBy, reset, pointerHandlers} = useZoomPan(container, zoom ?? ownZoom);
  const previewWidth = image.current?.naturalWidth || width;
  const wantFull = needsFullImage(view.scale, image.current?.clientWidth ?? 0, previewWidth, width * height);
  const source = useProgressiveSource(previewUrl, fullUrl, wantFull);
  return (
    <div className="mosaic-viewer">
      <div ref={container} className="mosaic-viewer__stage" {...pointerHandlers}>
        <img ref={image} className="mosaic-viewer__image" src={source} alt={alt} draggable={false}
          style={{transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`}} />
      </div>
      <div className="mosaic-viewer__controls" aria-label="Zoom del mosaico">
        <button type="button" className="icon-button" aria-label="Acercar" onClick={() => zoomBy(ZOOM_STEP)}>+</button>
        <button type="button" className="icon-button" aria-label="Alejar" onClick={() => zoomBy(1 / ZOOM_STEP)}>−</button>
        <button type="button" className="icon-button icon-button--wide" onClick={reset}>Ajustar</button>
      </div>
    </div>
  );
}
