// Estado de una subida (lote u objetivo): progreso y error. Al empezar una
// subida nueva se descarta solo ese recurso; el otro queda como estaba.

import {useState} from 'react';
import type {UploadProgress} from '../api/client';

export type UploadTask<T> = (onProgress: UploadProgress) => Promise<T>;

export interface Upload<T>
{
  /** Fracción subida, o `null` si no hay una subida en curso. */
  progress: number | null;
  error: string | null;
  start: (task: UploadTask<T>) => void;
  fail: (message: string) => void;
}

export function useUpload<T>(onDiscard: () => void, onDone: (result: T) => void): Upload<T>
{
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const start = (task: UploadTask<T>): void =>
  {
    onDiscard();
    setError(null);
    setProgress(0);
    task(setProgress)
      .then(onDone)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setProgress(null));
  };
  return {progress, error, start, fail: setError};
}
