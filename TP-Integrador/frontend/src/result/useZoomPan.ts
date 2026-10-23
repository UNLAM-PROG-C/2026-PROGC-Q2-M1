// Hook del visor: zoom con la rueda (sobre el cursor) y arrastre con el puntero.
// La rueda se escucha con `passive: false` para poder evitar el scroll de la página.
// La vista vive en un `ZoomController`: si dos visores comparten el mismo, se mueven juntos.

import {useEffect, useRef, useSyncExternalStore, type PointerEvent, type RefObject} from 'react';
import {FIT_VIEW, panBy, zoomAt, ZOOM_STEP, type Point, type ZoomView} from './zoom';
import type {ZoomController} from './zoomController';

export interface ZoomPan
{
  view: ZoomView;
  zoomBy: (factor: number) => void;
  reset: () => void;
  pointerHandlers: {onPointerDown: (event: PointerEvent) => void; onPointerMove: (event: PointerEvent) => void; onPointerUp: () => void};
}

const HALF_DIVISOR = 2;

function centerOf(element: HTMLElement | null): Point
{
  const rect = element?.getBoundingClientRect();
  return rect ? {x: rect.width / HALF_DIVISOR, y: rect.height / HALF_DIVISOR} : {x: 0, y: 0};
}

function useWheelZoom(container: RefObject<HTMLElement | null>, setView: (update: (view: ZoomView) => ZoomView) => void): void
{
  useEffect(() =>
  {
    const element = container.current;
    const onWheel = (event: WheelEvent): void =>
    {
      event.preventDefault();
      const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
      const factor = event.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP;
      setView((view) => zoomAt(view, factor, {x: event.clientX - rect.left, y: event.clientY - rect.top}));
    };
    element?.addEventListener('wheel', onWheel, {passive: false});
    return () => element?.removeEventListener('wheel', onWheel);
  }, [container, setView]);
}

export function useZoomPan(container: RefObject<HTMLElement | null>, controller: ZoomController): ZoomPan
{
  const view = useSyncExternalStore(controller.subscribe, controller.getView);
  const setView = controller.update;
  const drag = useRef<Point | null>(null);
  useWheelZoom(container, setView);

  const onPointerDown = (event: PointerEvent): void =>
  {
    (event.currentTarget as Element).setPointerCapture?.(event.pointerId);
    drag.current = {x: event.clientX, y: event.clientY};
  };
  const onPointerMove = (event: PointerEvent): void =>
  {
    const start = drag.current;
    if (start)
    {
      drag.current = {x: event.clientX, y: event.clientY};
      setView((current) => panBy(current, event.clientX - start.x, event.clientY - start.y));
    }
  };
  const zoomBy = (factor: number): void => setView((current) => zoomAt(current, factor, centerOf(container.current)));
  return {view, zoomBy, reset: () => setView(() => FIT_VIEW), pointerHandlers: {onPointerDown, onPointerMove, onPointerUp: () => (drag.current = null)}};
}
