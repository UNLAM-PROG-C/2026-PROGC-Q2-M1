// Zonas de carga del paso 1 con su progreso de subida, error y resumen.

import {targetImageUrl, tileSampleUrl} from '../api/client';
import type {TargetSummary, TilesSummary} from '../api/types';
import {FileDropZone} from '../components/FileDropZone';
import {ImageThumb} from '../components/ImageThumb';
import {ProgressBar} from '../components/ProgressBar';
import {targetSummaryText, tilesSummaryText} from './imagesText';
import type {Upload} from './useUpload';

const IMAGE_ACCEPT = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp';
const TILES_ACCEPT = `${IMAGE_ACCEPT},.zip,application/zip`;

function UploadStatus<T>({upload, label}: {upload: Upload<T>; label: string}): JSX.Element | null
{
  if (upload.progress !== null)
  {
    return <ProgressBar label={label} fraction={upload.progress} />;
  }
  return upload.error ? <p className="field-error" role="alert">{upload.error}</p> : null;
}

function TilesPreview({tiles}: {tiles: TilesSummary}): JSX.Element
{
  return (
    <div className="upload-summary">
      <p className="upload-summary__text">{tilesSummaryText(tiles)}</p>
      <div className="upload-summary__thumbs">
        {tiles.samples.map((name, index) => <ImageThumb key={name} src={tileSampleUrl(tiles.tiles_id, index)} alt={name} />)}
      </div>
    </div>
  );
}

interface ZoneProps<T>
{
  upload: Upload<T>;
  onFiles: (files: File[]) => void;
}

export function TilesZone({tiles, upload, onFiles}: ZoneProps<TilesSummary> & {tiles: TilesSummary | null}): JSX.Element
{
  return (
    <FileDropZone title="Lote de teselas" hint="Varias imágenes JPEG, PNG o WebP, o un único .zip" accept={TILES_ACCEPT} multiple
      disabled={upload.progress !== null} onFiles={onFiles}>
      <UploadStatus upload={upload} label="Subida del lote" />
      {tiles && <TilesPreview tiles={tiles} />}
    </FileDropZone>
  );
}

export function TargetZone({target, upload, onFiles}: ZoneProps<TargetSummary> & {target: TargetSummary | null}): JSX.Element
{
  return (
    <FileDropZone title="Imagen objetivo" hint="Una imagen JPEG, PNG o WebP" accept={IMAGE_ACCEPT} multiple={false}
      disabled={upload.progress !== null} onFiles={onFiles}>
      <UploadStatus upload={upload} label="Subida del objetivo" />
      {target && (
        <div className="upload-summary">
          <ImageThumb src={targetImageUrl(target.target_id)} alt={target.filename} large />
          <p className="upload-summary__text">{targetSummaryText(target)}</p>
        </div>
      )}
    </FileDropZone>
  );
}
