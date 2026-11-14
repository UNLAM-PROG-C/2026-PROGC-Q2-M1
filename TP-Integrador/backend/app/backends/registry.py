"""Detección, estado y selección de backends (spec deteccion-de-backends, design D7).

Patrón Factory: cada backend se crea con una fábrica que importa su biblioteca
(PyCUDA, PyOpenCL) **dentro** de la llamada, así importar el proyecto nunca falla
en una máquina sin GPU. ``detect_and_warmup()`` crea y precalienta cada backend;
cualquier excepción deja a ese backend como no disponible con un motivo corto,
el detalle completo (por ejemplo, el build log) va al log y se sigue con los
demás.

Diagnóstico: ``python -m app.backends.registry`` (desde ``backend/``) imprime el
estado de todos los backends y la GPU preferida.
"""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from app.core.backend import BackendInitError, MosaicBackend

CPU = "cpu"
CUDA = "cuda"
OPENCL = "opencl"
DISPLAY_NAMES = {CPU: "CPU secuencial", CUDA: "CUDA", OPENCL: "OpenCL"}
# GPUs en orden de preferencia para la opción "GPU" de la interfaz.
GPU_PREFERENCE = (CUDA, OPENCL)
REASON_NOT_INSTALLED = "biblioteca no instalada"
REASON_DRIVER = "error de driver"
REASON_NO_GPU = "no se detectó una GPU compatible"
REASON_UNKNOWN = "backend desconocido"
CPU_ALWAYS_AVAILABLE = "siempre disponible"
LOG_FORMAT = "%(levelname)s %(name)s: %(message)s"

BackendFactory = Callable[[], MosaicBackend]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackendStatus:
  """Estado informable de un backend, disponible o no."""

  name: str
  available: bool
  device_name: str | None = None
  reason: str | None = None
  init_ms: float | None = None
  warnings: tuple[str, ...] = ()

  @property
  def display_name(self) -> str:
    """Nombre para mostrar ("CUDA", "OpenCL", "CPU secuencial")."""
    return DISPLAY_NAMES.get(self.name, self.name)

  def describe(self) -> str:
    """Una línea: "CUDA: <dispositivo>", "OpenCL: no disponible (motivo)"..."""
    if not self.available:
      return f"{self.display_name}: no disponible ({self.reason})"
    if self.name == CPU:
      return f"{self.display_name}: {CPU_ALWAYS_AVAILABLE} ({self.device_name})"
    return f"{self.display_name}: {self.device_name}"


@dataclass(frozen=True)
class GpuPreference:
  """GPU que usa la opción "GPU" de la interfaz, o el motivo de que no haya."""

  status: BackendStatus | None
  reason: str | None = None


class BackendUnavailableError(RuntimeError):
  """Se pidió un backend desconocido o no disponible; el trabajo se rechaza."""


def _create_cpu() -> MosaicBackend:
  """Fábrica del backend CPU secuencial."""
  from app.backends.cpu.backend import CpuBackend  # Import diferido (Factory).

  return CpuBackend()


def _create_cuda() -> MosaicBackend:
  """Fábrica del backend CUDA (importa PyCUDA recién acá)."""
  from app.backends.cuda.backend import CudaBackend  # Import diferido.

  return CudaBackend()


def _create_opencl() -> MosaicBackend:
  """Fábrica del backend OpenCL (importa PyOpenCL recién acá)."""
  from app.backends.opencl.backend import OpenClBackend  # Import diferido.

  return OpenClBackend()


DEFAULT_FACTORIES: dict[str, BackendFactory] = {CPU: _create_cpu, CUDA: _create_cuda, OPENCL: _create_opencl}


def failure_reason(error: Exception) -> str:
  """Motivo corto de una falla de inicialización."""
  if isinstance(error, BackendInitError):
    return error.reason
  if isinstance(error, ModuleNotFoundError):
    return REASON_NOT_INSTALLED
  return REASON_DRIVER


def _log_failure(name: str, error: Exception) -> None:
  """Registra la falla: completa (con traza y build log) salvo que falte la biblioteca."""
  if isinstance(error, ModuleNotFoundError):
    logger.info("%s no disponible: %s", DISPLAY_NAMES.get(name, name), error)
    return
  logger.error("%s no disponible: %s", DISPLAY_NAMES.get(name, name), error, exc_info=error)


def _close(backend: MosaicBackend) -> None:
  """Cierra el backend si tiene recursos que liberar (los GPU tienen ``close()``)."""
  close = getattr(backend, "close", None)
  if close is not None:
    close()


class BackendRegistry:
  """Conoce el estado de cada backend y resuelve cuál ejecuta un trabajo."""

  def __init__(self, factories: dict[str, BackendFactory] | None = None) -> None:
    """``factories`` reemplaza las fábricas reales (tests)."""
    self._factories = dict(DEFAULT_FACTORIES if factories is None else factories)
    self._backends: dict[str, MosaicBackend] = {}
    self._statuses: dict[str, BackendStatus] = {}

  def __enter__(self) -> "BackendRegistry":
    """Permite usar el registro con ``with``."""
    return self

  def __exit__(self, *exc_info: object) -> None:
    """Libera los backends al salir del ``with``."""
    self.close()

  def detect_and_warmup(self) -> list[BackendStatus]:
    """Crea y precalienta cada backend; las fallas quedan aisladas en su estado."""
    for name, factory in self._factories.items():
      self._statuses[name] = self._detect(name, factory)
    return self.statuses()

  def _detect(self, name: str, factory: BackendFactory) -> BackendStatus:
    """Estado de un backend después de intentar crearlo y precalentarlo."""
    backend = None
    try:
      backend = factory()
      backend.warmup()
    except Exception as error:
      _log_failure(name, error)
      if backend is not None:
        _close(backend)
      return BackendStatus(name, available=False, reason=failure_reason(error))
    self._backends[name] = backend
    warnings = tuple(getattr(backend, "warnings", ()))
    return BackendStatus(name, True, backend.device_name, init_ms=backend.init_ms, warnings=warnings)

  def statuses(self) -> list[BackendStatus]:
    """Estado de todos los backends detectados, en orden de registro."""
    return [self._statuses[name] for name in self._factories if name in self._statuses]

  def status(self, name: str) -> BackendStatus:
    """Estado de un backend (no disponible con motivo si es desconocido)."""
    return self._statuses.get(name, BackendStatus(name, available=False, reason=REASON_UNKNOWN))

  def resolve(self, names: Iterable[str]) -> list[MosaicBackend]:
    """Backends pedidos, exactamente esos; rechaza los no disponibles sin sustituirlos."""
    resolved = []
    for name in names:
      status = self.status(name)
      if not status.available:
        raise BackendUnavailableError(status.describe())
      resolved.append(self._backends[name])
    return resolved

  def preferred_gpu(self) -> GpuPreference:
    """CUDA si está disponible, si no OpenCL; nunca CPU."""
    for name in GPU_PREFERENCE:
      status = self.status(name)
      if status.available:
        return GpuPreference(status)
    reasons = "; ".join(f"{DISPLAY_NAMES[name]}: {self.status(name).reason}" for name in GPU_PREFERENCE)
    return GpuPreference(None, f"{REASON_NO_GPU} ({reasons})")

  def close(self) -> None:
    """Cierra todos los backends creados (libera contextos de GPU)."""
    for backend in self._backends.values():
      _close(backend)
    self._backends.clear()


def _status_lines(status: BackendStatus) -> list[str]:
  """Líneas del diagnóstico de un backend."""
  lines = [status.describe()]
  if status.available:
    lines.append(f"  inicialización: {status.init_ms:.1f} ms")
  lines.extend(f"  advertencia: {warning}" for warning in status.warnings)
  return lines


def main() -> None:
  """Imprime el estado de todos los backends y la GPU preferida."""
  logging.basicConfig(level=logging.WARNING, format=LOG_FORMAT)
  with BackendRegistry() as registry:
    for status in registry.detect_and_warmup():
      print("\n".join(_status_lines(status)))
    preference = registry.preferred_gpu()
    chosen = preference.status.describe() if preference.status else preference.reason
    print(f"GPU preferida: {chosen}")


if __name__ == "__main__":
  main()
