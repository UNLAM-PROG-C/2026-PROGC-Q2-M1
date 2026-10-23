// Matemática del zoom y el desplazamiento del visor, sin DOM.
// La imagen se transforma con `translate(x, y) scale(scale)` y origen arriba
// a la izquierda; acercar sobre un punto lo deja fijo debajo del cursor.

export interface ZoomView
{
  scale: number;
  x: number;
  y: number;
}

export interface Point
{
  x: number;
  y: number;
}

export const MIN_ZOOM = 1;
export const MAX_ZOOM = 32;
/** Factor de zoom por cada paso de la rueda o de los botones. */
export const ZOOM_STEP = 1.25;
/** Por encima de esta cantidad de píxeles no se carga el PNG completo: se queda la vista previa. */
export const FULL_IMAGE_MAX_PIXELS = 40_000_000;

export const FIT_VIEW: ZoomView = {scale: MIN_ZOOM, x: 0, y: 0};

export function clampScale(scale: number): number
{
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, scale));
}

/** Multiplica el zoom por `factor` manteniendo fijo `point` (coordenadas del visor). */
export function zoomAt(view: ZoomView, factor: number, point: Point): ZoomView
{
  const scale = clampScale(view.scale * factor);
  if (scale === MIN_ZOOM)
  {
    return FIT_VIEW;
  }
  const ratio = scale / view.scale;
  return {scale, x: point.x - (point.x - view.x) * ratio, y: point.y - (point.y - view.y) * ratio};
}

export function panBy(view: ZoomView, dx: number, dy: number): ZoomView
{
  return view.scale === MIN_ZOOM ? view : {...view, x: view.x + dx, y: view.y + dy};
}

/**
 * Hace falta la imagen completa cuando la vista previa, agrandada, ya muestra
 * menos de un píxel propio por píxel de pantalla, y la completa no es demasiado grande.
 */
export function needsFullImage(scale: number, displayedWidth: number, previewWidth: number, fullPixels: number): boolean
{
  return displayedWidth * scale > previewWidth && fullPixels <= FULL_IMAGE_MAX_PIXELS;
}
