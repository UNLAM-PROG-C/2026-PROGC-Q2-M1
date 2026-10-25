// Matemática del zoom y el desplazamiento del visor, sin DOM.
// La imagen se transforma con `translate(x, y) scale(scale)` y origen arriba
// a la izquierda; acercar sobre un punto lo deja fijo debajo del cursor.
// La vista de la persona (`ZoomView`) es relativa al encaje: escala 1 es el
// mosaico entero en el visor. `composeViews` la combina con `fitView`.

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
/**
 * Por encima de esta cantidad de píxeles no se carga el PNG completo: se queda la vista previa.
 * Coincide con el máximo de salida por defecto del backend (`MOSAIC_MAX_OUTPUT_PIXELS`): con la
 * configuración por defecto todo mosaico se puede ver completo al acercar. Con un límite menor,
 * un mosaico de 200 columnas × 64 px (12.800 × 9.600) quedaba en la vista previa de 2048 px
 * y al acercar se veía borroso.
 */
export const FULL_IMAGE_MAX_PIXELS = 150_000_000;

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

const CENTER_DIVISOR = 2;

/**
 * Encaje de una imagen de `imageWidth × imageHeight` en la caja del visor, centrada y
 * sin deformar (como `object-fit: contain`). La escala es "píxeles CSS por píxel de la imagen".
 */
export function fitView(boxWidth: number, boxHeight: number, imageWidth: number, imageHeight: number): ZoomView
{
  if (imageWidth <= 0 || imageHeight <= 0)
  {
    return FIT_VIEW;
  }
  const scale = Math.min(boxWidth / imageWidth, boxHeight / imageHeight);
  return {scale, x: (boxWidth - imageWidth * scale) / CENTER_DIVISOR, y: (boxHeight - imageHeight * scale) / CENTER_DIVISOR};
}

/**
 * Transformación final de la imagen: primero el encaje y después el zoom de la persona,
 * que está expresado en coordenadas del visor (`zoomAt` y `panBy` no cambian).
 */
export function composeViews(view: ZoomView, fit: ZoomView): ZoomView
{
  return {scale: view.scale * fit.scale, x: view.x + view.scale * fit.x, y: view.y + view.scale * fit.y};
}

/**
 * Hace falta la imagen completa cuando la vista previa, agrandada, ya muestra
 * menos de un píxel propio por píxel físico de pantalla, y la completa no es demasiado grande.
 * `displayedWidth` va en píxeles físicos (CSS × devicePixelRatio): en una pantalla Retina
 * la vista previa se queda corta mucho antes que en una común.
 */
export function needsFullImage(scale: number, displayedWidth: number, previewWidth: number, fullPixels: number): boolean
{
  return displayedWidth * scale > previewWidth && fullPixels <= FULL_IMAGE_MAX_PIXELS;
}

/** Pasado 1:1 con la resolución completa, cada píxel del mosaico ocupa varios de pantalla. */
export function showsRealPixels(scale: number, displayedWidth: number, fullWidth: number): boolean
{
  return displayedWidth * scale > fullWidth;
}
