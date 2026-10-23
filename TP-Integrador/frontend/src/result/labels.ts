// Nombres legibles de los backends para el resultado y las estadísticas.

import type {BackendName} from '../api/types';

const BACKEND_LABELS: Readonly<Record<BackendName, string>> = {
  cpu: 'CPU',
  cuda: 'GPU — CUDA',
  opencl: 'GPU — OpenCL',
};

/** Nombre corto de cada backend, como en "OpenCL: 3 celdas difieren de CPU". */
export const BACKEND_SHORT_NAMES: Readonly<Record<BackendName, string>> = {
  cpu: 'CPU',
  cuda: 'CUDA',
  opencl: 'OpenCL',
};

export function backendLabel(backend: BackendName, device: string | null): string
{
  return device ? `${BACKEND_LABELS[backend]} (${device})` : BACKEND_LABELS[backend];
}

/** "CPU" o "GPU", sin la API: así se nombra a cada lado de una comparación. */
export function backendKind(backend: BackendName): string
{
  return backend === 'cpu' ? 'CPU' : 'GPU';
}

/** Por ejemplo "GPU falló: memoria insuficiente en el dispositivo". */
export function failureText(backend: BackendName, reason: string): string
{
  return `${backendKind(backend)} falló: ${reason}`;
}
