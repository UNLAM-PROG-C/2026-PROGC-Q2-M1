// Visor del mosaico: muestra la vista previa reducida y permite acercar con la
// rueda (o los botones) y arrastrar. Pasado cierto zoom, si el mosaico no es
// gigante, carga el PNG completo en segundo plano y lo reemplaza al terminar
// (spec "Resultado con zoom"). Con `zoom` comparte la vista con otro visor
// (comparación del cambio 4); sin él usa un controlador propio. `children` se
// suma al final de la fila de zoom (la descarga de ese mosaico).
// La imagen mide en el DOM lo mismo que el mosaico completo y se achica con
// `scale()` para encajar: si midiera lo que el visor, el navegador la
// decodificaría y dibujaría a ese tamaño y al acercar se vería borrosa.
// Pasado 1:1 con la imagen completa se dibuja sin suavizar (`pixelated`), así
// los bordes de cada tesela se ven nítidos.

import {useEffect, useRef, useState, type ReactNode, type RefObject} from 'react';
import {composeViews, fitView, needsFullImage, showsRealPixels, ZOOM_STEP, type ZoomView} from './zoom';
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
  /** Controles extra al final de la fila de zoom (la descarga). */
  children?: ReactNode;
}

interface Size
{
  width: number;
  height: number;
}

/** Tamaño del escenario, actualizado al cambiar la ventana o el layout. */
function useElementSize(element: RefObject<HTMLElement>): Size
{
  const [size, setSize] = useState<Size>({width: 0, height: 0});
  useEffect(() =>
  {
    const target = element.current;
    if (!target || typeof ResizeObserver === 'undefined')
    {
      return;
    }
    const observer = new ResizeObserver(() => setSize({width: target.clientWidth, height: target.clientHeight}));
    observer.observe(target);
    return () => observer.disconnect();
  }, [element]);
  return size;
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

interface ViewerImage
{
  source: string;
  className: string;
  transform: string;
}

function useViewerImage(props: MosaicViewerProps, view: ZoomView, stage: RefObject<HTMLElement>, image: RefObject<HTMLImageElement>): ViewerImage
{
  const {previewUrl, fullUrl, width, height} = props;
  const box = useElementSize(stage);
  const fit = fitView(box.width, box.height, width, height);
  const fitDeviceWidth = width * fit.scale * window.devicePixelRatio;
  const previewWidth = image.current?.naturalWidth || width;
  const source = useProgressiveSource(previewUrl, fullUrl, needsFullImage(view.scale, fitDeviceWidth, previewWidth, width * height));
  const sharp = source === fullUrl && showsRealPixels(view.scale, fitDeviceWidth, width);
  const shown = composeViews(view, fit);
  return {
    source,
    className: sharp ? 'mosaic-viewer__image mosaic-viewer__image--pixelated' : 'mosaic-viewer__image',
    transform: `translate(${shown.x}px, ${shown.y}px) scale(${shown.scale})`,
  };
}

export function MosaicViewer(props: MosaicViewerProps): JSX.Element
{
  const container = useRef<HTMLDivElement>(null);
  const image = useRef<HTMLImageElement>(null);
  const [ownZoom] = useState(() => new ZoomController());
  const {view, zoomBy, reset, pointerHandlers} = useZoomPan(container, props.zoom ?? ownZoom);
  const {source, className, transform} = useViewerImage(props, view, container, image);
  return (
    <div className="mosaic-viewer">
      <div ref={container} className="mosaic-viewer__stage" {...pointerHandlers}>
        <img ref={image} className={className} src={source} alt={props.alt} draggable={false}
          style={{width: `${props.width}px`, height: `${props.height}px`, transform}} />
      </div>
      <div className="mosaic-viewer__controls" aria-label="Controles del mosaico">
        <button type="button" className="icon-button" aria-label="Acercar" onClick={() => zoomBy(ZOOM_STEP)}>+</button>
        <button type="button" className="icon-button" aria-label="Alejar" onClick={() => zoomBy(1 / ZOOM_STEP)}>−</button>
        <button type="button" className="icon-button icon-button--wide" onClick={reset}>Ajustar</button>
        {props.children}
      </div>
    </div>
  );
}
