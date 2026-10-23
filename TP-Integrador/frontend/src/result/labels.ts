// Nombres legibles de los backends para el resultado y las estadísticas.

import type {BackendName} from '../api/types';

const BACKEND_LABELS: Readonly<Record<BackendName, string>> = {
  cpu: 'CPU',
  cuda: 'GPU — CUDA',
  opencl: 'GPU — OpenCL',
};

export function backendLabel(backend: BackendName, device: string | null): string
{
  return device ? `${BACKEND_LABELS[backend]} (${device})` : BACKEND_LABELS[backend];
}
