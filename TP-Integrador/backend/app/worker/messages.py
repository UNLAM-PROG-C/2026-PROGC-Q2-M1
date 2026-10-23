"""Protocolo entre el proceso web y el worker (design D2).

Patrones:
- Command: ``RunJob`` y ``Shutdown`` son órdenes autocontenidas que el proceso
  web encola y el worker ejecuta en su único hilo de trabajo.
- Productor/Consumidor: la web produce órdenes en ``command_q`` y consume
  eventos de ``event_q``; el worker hace lo inverso.

Todos los mensajes son dataclasses congeladas que se serializan con pickle.
Nunca viajan arrays de imágenes: los resultados se escriben a disco y se
informan por ruta (spec "Mensajes livianos entre procesos").
"""

from dataclasses import dataclass

from app.backends.cpu.calibration import CpuCalibration
from app.backends.registry import BackendStatus, GpuPreference
from app.core.params import MosaicParams
from app.core.result import StageTimings

# Etapas propias del worker que se suman a las de los backends en el progreso.
STAGE_LOAD = "load"
STAGE_SAVE = "save"

# --- web → worker ---------------------------------------------------------------


@dataclass(frozen=True)
class RunJob:
  """Ejecutar un trabajo con una lista explícita de backends (el cambio 4 pasa dos)."""

  job_id: str
  tiles_dir: str
  target_path: str
  params: MosaicParams
  backends: tuple[str, ...]
  output_dir: str


@dataclass(frozen=True)
class Shutdown:
  """Cerrar el pool, liberar los contextos de GPU y salir."""


# --- worker → web ---------------------------------------------------------------


@dataclass(frozen=True)
class WorkerReady:
  """Backends detectados y precalentados; recién ahora se aceptan trabajos."""

  statuses: tuple[BackendStatus, ...]
  preferred_gpu: GpuPreference
  calibration: CpuCalibration | None


@dataclass(frozen=True)
class JobProgress:
  """Avance de una etapa; ``backend`` es ``None`` en la carga común."""

  job_id: str
  backend: str | None
  stage: str
  fraction: float


@dataclass(frozen=True)
class LoadFinished:
  """Fin de la carga común (se mide aparte de los backends)."""

  job_id: str
  load_ms: float
  reused: bool
  n_tiles: int
  skipped_files: int
  rows: int
  cols: int
  m_cells: int


@dataclass(frozen=True)
class BackendFinished:
  """Un backend terminó: tiempos y rutas de la imagen guardada."""

  job_id: str
  backend: str
  device: str
  timings: StageTimings
  init_ms: float | None
  png_path: str
  jpeg_path: str
  preview_path: str
  width: int
  height: int


@dataclass(frozen=True)
class JobFinished:
  """Todos los backends del trabajo terminaron."""

  job_id: str


@dataclass(frozen=True)
class JobFailed:
  """El trabajo falló; ``reason`` es legible para la interfaz."""

  job_id: str
  reason: str


@dataclass(frozen=True)
class JobRejected:
  """El worker recibió un ``RunJob`` mientras ejecutaba otro y no lo aceptó."""

  job_id: str
  reason: str


# --- local del proceso web ------------------------------------------------------


@dataclass(frozen=True)
class WorkerCrashed:
  """El monitor de ``WorkerClient`` vio morir al worker (no cruza procesos)."""

  exitcode: int | None


Command = RunJob | Shutdown
WorkerEvent = WorkerReady | JobProgress | LoadFinished | BackendFinished | JobFinished | JobFailed | JobRejected
