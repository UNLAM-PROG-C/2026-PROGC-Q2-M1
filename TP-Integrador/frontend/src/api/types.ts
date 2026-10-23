// DTOs de la API HTTP y eventos del WebSocket (design D2, D4 y D5).
// Los nombres de los campos siguen el JSON del backend (snake_case) para no
// tener que traducirlos: este archivo es el contrato entre ambos lados.

/** Forma de ejecución que elige la persona (design D4). */
export type ExecutionMode = 'cpu' | 'gpu';

/** Nombre de un backend concreto del registro (cambio 2). */
export type BackendName = 'cpu' | 'cuda' | 'opencl';

/** API de GPU que eligió el registro con `preferred_gpu()`. */
export type GpuApi = 'CUDA' | 'OpenCL';

/** Etapas que informa el progreso, en orden de ejecución. */
export type ProgressStage = 'load' | 'prepare_tiles' | 'target_descriptors' | 'matching' | 'compose' | 'save';

/** Formatos de archivo de un resultado. */
export type ResultKind = 'preview' | 'png' | 'jpg';

/** Estado de un backend detectado por el worker (`BackendStatus` del cambio 2). */
export interface BackendStatus
{
  name: BackendName;
  available: boolean;
  device_name: string | null;
  reason: string | null;
  init_ms: number | null;
  warnings: string[];
}

/** Opción "CPU" del paso 3. */
export interface CpuOption
{
  available: boolean;
  device: string | null;
}

/** Opción "GPU" del paso 3, ya resuelta por el backend (design D4). */
export interface GpuOption
{
  available: boolean;
  api: GpuApi | null;
  device: string | null;
  reason: string | null;
}

export interface ExecutionOptions
{
  cpu: CpuOption;
  gpu: GpuOption;
}

/** Costos unitarios medidos al iniciar el worker (design D8), en nanosegundos. */
export interface CpuCalibration
{
  matching_ns_per_pair: number;
  prepare_ns_per_pixel: number;
  compose_ns_per_pixel: number;
}

export interface IntRange
{
  min: number;
  max: number;
  default: number;
}

/** Reglas de validación de parámetros: vienen del backend para no duplicar constantes. */
export interface ParamRules
{
  cols: IntRange;
  tile_px: {allowed: number[]; default: number};
  alpha: {min: number; max: number; default: number};
  seed: IntRange;
  max_output_pixels: number;
  cpu_confirm_seconds: number;
}

/** Resumen de un lote subido. `samples` son nombres de archivo de la muestra. */
export interface TilesSummary
{
  tiles_id: string;
  accepted: number;
  ignored: number;
  rejected: number;
  samples: string[];
}

/** Respuesta de `POST /api/tiles`. */
export interface TilesUploadResponse
{
  tiles_id: string;
  accepted: number;
  ignored: number;
  rejected: number;
}

/** Imagen objetivo subida (respuesta de `POST /api/targets` y parte de `/api/state`). */
export interface TargetSummary
{
  target_id: string;
  filename: string;
  width: number;
  height: number;
}

/** Parámetros del trabajo tal como viajan a `POST /api/jobs`. */
export interface JobParams
{
  cols: number;
  tile_px: number;
  alpha: number;
  seed: number;
}

export interface JobRequest extends JobParams
{
  tiles_id: string;
  target_id: string;
  mode: ExecutionMode;
}

export interface JobCreatedResponse
{
  job_id: string;
  backends: BackendName[];
}

/** Datos de la carga común (`LoadFinished`). */
export interface LoadInfo
{
  load_ms: number;
  reused: boolean;
  n_tiles: number;
  skipped_files: number;
  rows: number;
  cols: number;
  m_cells: number;
}

/** Tiempos por etapa en ms (`asdict(StageTimings)`); `null` significa "no aplica". */
export interface StageTimings
{
  prepare_tiles_ms: number;
  target_descriptors_ms: number;
  matching_ms: number;
  compose_ms: number;
  total_ms: number;
  transfer_h2d_ms: number | null;
  transfer_d2h_ms: number | null;
  staging_h2d_ms: number | null;
  staging_d2h_ms: number | null;
}

/** Resultado de un backend (`BackendFinished`). */
export interface BackendResult
{
  backend: BackendName;
  device: string;
  timings: StageTimings;
  init_ms: number | null;
  width: number;
  height: number;
}

export interface JobProgressInfo
{
  backend: BackendName | null;
  stage: ProgressStage;
  fraction: number;
}

export type JobStatus = 'running' | 'finished' | 'failed';

/** Trabajo en curso o último trabajo terminado (snapshot de design D5). */
export interface JobSnapshot
{
  job_id: string;
  status: JobStatus;
  mode: ExecutionMode;
  backends: BackendName[];
  tiles_id: string;
  target_id: string;
  params: JobParams & {k: number};
  progress: JobProgressInfo | null;
  load: LoadInfo | null;
  results: BackendResult[];
  error: string | null;
}

export interface WorkerInfo
{
  ready: boolean;
  error: string | null;
}

/** Respuesta de `GET /api/state` y snapshot que llega al conectar el WebSocket. */
export interface AppState
{
  worker: WorkerInfo;
  backends: BackendStatus[];
  execution: ExecutionOptions;
  calibration: CpuCalibration | null;
  rules: ParamRules;
  job: JobSnapshot | null;
  last_tiles: TilesSummary | null;
  last_target: TargetSummary | null;
}

// --- Mensajes del WebSocket (servidor → navegador) -------------------------

export interface StateEvent
{
  type: 'state';
  state: AppState;
}

export interface JobStartedEvent
{
  type: 'job_started';
  job: JobSnapshot;
}

export interface JobProgressEvent extends JobProgressInfo
{
  type: 'job_progress';
  job_id: string;
}

export interface LoadFinishedEvent
{
  type: 'load_finished';
  job_id: string;
  load: LoadInfo;
}

export interface BackendFinishedEvent
{
  type: 'backend_finished';
  job_id: string;
  result: BackendResult;
}

export interface JobFinishedEvent
{
  type: 'job_finished';
  job_id: string;
}

export interface JobFailedEvent
{
  type: 'job_failed';
  job_id: string;
  reason: string;
}

export interface WorkerStatusEvent
{
  type: 'worker_status';
  worker: WorkerInfo;
}

export type ServerEvent =
  | StateEvent
  | JobStartedEvent
  | JobProgressEvent
  | LoadFinishedEvent
  | BackendFinishedEvent
  | JobFinishedEvent
  | JobFailedEvent
  | WorkerStatusEvent;
