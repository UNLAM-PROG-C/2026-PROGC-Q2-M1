// Cliente HTTP del backend (patrón Facade, design D13): el resto de la interfaz
// no arma URLs ni maneja fetch/XHR, solo llama a estas funciones.
// Las subidas usan XMLHttpRequest porque fetch no informa el progreso de envío.

import {BACKEND_URL} from './config';
import type {AppState, BackendName, JobCreatedResponse, JobRequest, ResultKind, TargetSummary, TilesSummary, TilesUploadResponse} from './types';

const HTTP_OK_MIN = 200;
const HTTP_OK_MAX = 299;
const ZIP_EXTENSION = '.zip';

/** Error de la API con el código HTTP y el motivo legible que mandó el backend. */
export class ApiError extends Error
{
  constructor(readonly status: number, message: string)
  {
    super(message);
    this.name = 'ApiError';
  }
}

/** Fracción subida, entre 0 y 1. */
export type UploadProgress = (fraction: number) => void;

function isOk(status: number): boolean
{
  return status >= HTTP_OK_MIN && status <= HTTP_OK_MAX;
}

/** Extrae el motivo de un cuerpo de error de FastAPI (`{detail: string | [{msg}]}`). */
export function errorMessage(body: unknown, status: number): string
{
  const detail = (body as {detail?: unknown} | null)?.detail;
  if (typeof detail === 'string')
  {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0)
  {
    return detail.map((item) => (item as {msg?: string}).msg ?? String(item)).join('; ');
  }
  return `error del servidor (${status})`;
}

function parseJson(text: string): unknown
{
  try
  {
    return text ? JSON.parse(text) : null;
  }
  catch
  {
    return null;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T>
{
  const response = await fetch(`${BACKEND_URL}${path}`, init);
  const body = parseJson(await response.text());
  if (!isOk(response.status))
  {
    throw new ApiError(response.status, errorMessage(body, response.status));
  }
  return body as T;
}

function sendForm<T>(path: string, form: FormData, onProgress?: UploadProgress): Promise<T>
{
  return new Promise<T>((resolve, reject) =>
  {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BACKEND_URL}${path}`);
    xhr.upload.onprogress = (event) => event.lengthComputable && onProgress?.(event.loaded / event.total);
    xhr.onerror = () => reject(new ApiError(0, 'no se pudo conectar con el backend'));
    xhr.onload = () =>
    {
      const body = parseJson(xhr.responseText);
      return isOk(xhr.status) ? resolve(body as T) : reject(new ApiError(xhr.status, errorMessage(body, xhr.status)));
    };
    xhr.send(form);
  });
}

export function isZip(file: File): boolean
{
  return file.name.toLowerCase().endsWith(ZIP_EXTENSION);
}

/** Arma el multipart del lote: un único `.zip` va en `zip`; si no, cada archivo en `files`. */
export function buildTilesForm(files: File[]): FormData
{
  const form = new FormData();
  if (files.length === 1 && isZip(files[0]))
  {
    form.append('zip', files[0]);
    return form;
  }
  files.forEach((file) => form.append('files', file, file.name));
  return form;
}

export function getState(): Promise<AppState>
{
  return requestJson<AppState>('/api/state');
}

export function uploadTiles(files: File[], onProgress?: UploadProgress): Promise<TilesUploadResponse>
{
  return sendForm<TilesUploadResponse>('/api/tiles', buildTilesForm(files), onProgress);
}

export function getTiles(tilesId: string): Promise<TilesSummary>
{
  return requestJson<TilesSummary>(`/api/tiles/${encodeURIComponent(tilesId)}`);
}

export function uploadTarget(file: File, onProgress?: UploadProgress): Promise<TargetSummary>
{
  const form = new FormData();
  form.append('file', file, file.name);
  return sendForm<TargetSummary>('/api/targets', form, onProgress);
}

export function createJob(request: JobRequest): Promise<JobCreatedResponse>
{
  const init = {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(request)};
  return requestJson<JobCreatedResponse>('/api/jobs', init);
}

export function tileSampleUrl(tilesId: string, index: number): string
{
  return `${BACKEND_URL}/api/tiles/${encodeURIComponent(tilesId)}/samples/${index}`;
}

export function targetImageUrl(targetId: string): string
{
  return `${BACKEND_URL}/api/targets/${encodeURIComponent(targetId)}/image`;
}

export function resultUrl(jobId: string, backend: BackendName, kind: ResultKind): string
{
  return `${BACKEND_URL}/api/jobs/${encodeURIComponent(jobId)}/${backend}/${kind}`;
}
