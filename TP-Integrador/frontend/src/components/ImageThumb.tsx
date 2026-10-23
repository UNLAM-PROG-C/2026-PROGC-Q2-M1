// Miniatura de una imagen subida. El backend devuelve el archivo original y el
// navegador lo escala (design D5): el proceso web no decodifica imágenes.

interface ImageThumbProps
{
  src: string;
  alt: string;
  large?: boolean;
}

export function ImageThumb({src, alt, large = false}: ImageThumbProps): JSX.Element
{
  return <img className={large ? 'image-thumb image-thumb--large' : 'image-thumb'} src={src} alt={alt} loading="lazy" decoding="async" />;
}
