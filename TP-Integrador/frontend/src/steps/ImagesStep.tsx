// Paso 1: lote de teselas y la imagen objetivo, como recursos separados.
// Cada uno se sube apenas se elige (solo el que cambió) y queda a la vista su
// resumen; "Siguiente" se habilita cuando están los dos.

import type {Dispatch} from 'react';
import {getTiles, uploadTarget, uploadTiles} from '../api/client';
import type {TargetSummary, TilesSummary} from '../api/types';
import {StepActions} from '../components/StepActions';
import {StepTile} from '../components/StepTile';
import {stepBlocker, type WizardAction, type WizardState} from '../wizard/wizardReducer';
import {tilesSelectionError} from './imagesText';
import {TargetZone, TilesZone} from './ImageZones';
import {useUpload} from './useUpload';

interface ImagesStepProps
{
  wizard: WizardState;
  dispatch: Dispatch<WizardAction>;
}

export function ImagesStep({wizard, dispatch}: ImagesStepProps): JSX.Element
{
  const tilesUpload = useUpload<TilesSummary>(() => dispatch({type: 'TILES_DISCARDED'}), (tiles) => dispatch({type: 'TILES_UPLOADED', tiles}));
  const targetUpload = useUpload<TargetSummary>(() => dispatch({type: 'TARGET_DISCARDED'}), (target) => dispatch({type: 'TARGET_UPLOADED', target}));
  const uploading = tilesUpload.progress !== null || targetUpload.progress !== null;

  const onTiles = (files: File[]): void =>
  {
    const error = tilesSelectionError(files);
    if (error)
    {
      tilesUpload.fail(error);
      return;
    }
    tilesUpload.start((onProgress) => uploadTiles(files, onProgress).then((done) => getTiles(done.tiles_id)));
  };
  const onTarget = (files: File[]): void => targetUpload.start((onProgress) => uploadTarget(files[0], onProgress));
  const actions = <StepActions primaryLabel="Siguiente" onPrimary={() => dispatch({type: 'NEXT'})} blocker={uploading ? 'subiendo imágenes…' : stepBlocker(wizard)} />;

  return (
    <StepTile title="Imágenes" lead="Subí las fotos que van a formar el mosaico y la imagen que querés reproducir." actions={actions}>
      <div className="images-step">
        <TilesZone tiles={wizard.tiles} upload={tilesUpload} onFiles={onTiles} />
        <TargetZone target={wizard.target} upload={targetUpload} onFiles={onTarget} />
      </div>
    </StepTile>
  );
}
