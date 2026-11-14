// Textos de ayuda de los parámetros del paso 2 (spec interfaz-web,
// "Textos de ayuda de los parámetros"). Es el único lugar donde viven.

export type ParamKey = 'cols' | 'tilePx' | 'opacity' | 'seed';

export interface ParamHelp
{
  label: string;
  help: string;
}

export const PARAM_HELP: Readonly<Record<ParamKey, ParamHelp>> = {
  cols: {
    label: 'Columnas de la grilla',
    help: 'Cantidad de teselas a lo ancho del mosaico. Más columnas dan más detalle, pero el mosaico tarda más y la imagen final es más grande. ' +
      'Las filas se calculan solas según la proporción de la imagen objetivo.',
  },
  tilePx: {
    label: 'Resolución de cada tesela',
    help: 'Tamaño en píxeles con el que se dibuja cada tesela en el mosaico final. Más resolución da una imagen más nítida al hacer zoom, pero más pesada.',
  },
  opacity: {
    label: 'Opacidad de las teselas',
    help: 'Cuánto se ve la foto de cada tesela. Con 100 % se ven las fotos tal cual; con valores menores, cada tesela se tiñe con el color de esa zona ' +
      'de la imagen objetivo y el mosaico se parece más a ella.',
  },
  seed: {
    label: 'Semilla',
    help: 'Número que fija las elecciones al azar entre teselas parecidas. Con la misma semilla y los mismos parámetros se obtiene exactamente ' +
      'el mismo mosaico; cambiala para ver otra variante.',
  },
};
