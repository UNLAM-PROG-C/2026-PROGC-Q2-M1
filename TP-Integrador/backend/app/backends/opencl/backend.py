"""Backend OpenCL con PyOpenCL (spec backend-opencl, design D1/D4/D5/D6 del cambio 2).

- PyOpenCL se importa **dentro** del constructor: importar este módulo nunca
  falla, aunque no haya PyOpenCL ni GPU.
- Dispositivo: solo GPUs, AMD primero (ver ``device.py``).
- Una única command queue en orden, con ``PROFILING_ENABLE``: todos los
  comandos de un trabajo se encolan ahí y se miden con sus eventos.
- Staging con buffers ``ALLOC_HOST_PTR`` (memoria de host que el driver puede
  transferir por DMA): se mapean para escribir/leer desde el host y se copian
  buffer → buffer con ``enqueue_copy``, que es lo que se mide.
"""

import logging
import time
import warnings
from typing import Any

import numpy as np

from app.backends.gpu_base import (
  INPUT_NAMES,
  KERNEL_NAMES,
  REASON_KERNEL_BUILD,
  REASON_NO_OPENCL_GPU,
  GpuBackend,
  GpuStageTimer,
  job_buffer_sizes,
  pack_inputs,
)
from app.backends.kernel_build import OPENCL_SOURCE_NAME, define_options, load_kernel_source
from app.backends.opencl.device import configured_filter, display_name, select_gpu
from app.backends.opencl.timing import OpenClProfilingTimer
from app.core.backend import BackendInitError
from app.core.constants import OPENCL_MEMORY_FRACTION
from app.core.job import MosaicJob
from app.core.result import Stage
from app.core.timing import StageTimer, elapsed_ms_since

OPENCL_BACKEND_NAME = "opencl"
INPUT_STAGING = "input"
OUTPUT_STAGING = "output"
# Extensión de AMD que informa la memoria libre (en KiB).
AMD_FREE_MEMORY_EXTENSION = "cl_amd_device_attribute_query"
KIB = 1024
# Códigos de error de OpenCL que significan falta de memoria.
OUT_OF_MEMORY_CODES = ("MEM_OBJECT_ALLOCATION_FAILURE", "OUT_OF_RESOURCES", "OUT_OF_HOST_MEMORY", "INVALID_BUFFER_SIZE")

logger = logging.getLogger(__name__)


def opencl_available_bytes(global_mem: int, free_mem: int | None, reserved: int, fraction: float) -> int:
  """Bytes para la matriz de distancias (design D6).

  Si el dispositivo informa memoria libre (extensión de AMD) se parte de ella;
  si no, de la memoria global. En ambos casos se toma la fracción configurada y
  se descuenta lo ya reservado para el trabajo (OpenCL reserva de forma
  diferida, así que la memoria libre puede no reflejarlo todavía).
  """
  base = global_mem if free_mem is None else free_mem
  return int(base * fraction) - reserved


def _load_opencl() -> Any:
  """Importa PyOpenCL (``ImportError`` si no está instalado)."""
  import pyopencl as cl  # Import diferido: ver docstring del módulo.

  return cl


def _find_device(cl: Any) -> Any:
  """GPU elegida según ``device.py``; ``BackendInitError`` si no hay ninguna."""
  try:
    platforms = cl.get_platforms()
  except cl.Error as error:
    raise BackendInitError(REASON_NO_OPENCL_GPU, str(error)) from error
  device = select_gpu(platforms, cl.device_type.GPU, (cl.Error,), configured_filter())
  if device is None:
    raise BackendInitError(REASON_NO_OPENCL_GPU)
  return device


class OpenClBackend(GpuBackend):
  """Fotomosaico en una GPU con kernels OpenCL propios."""

  name = OPENCL_BACKEND_NAME

  def __init__(self, chunk_cells: int | None = None) -> None:
    """Elige la GPU y crea el contexto y la cola con profiling."""
    cl = _load_opencl()
    device = _find_device(cl)
    super().__init__(display_name(device, (cl.Error,)), chunk_cells)
    self._cl = cl
    self._device = device
    self._context = cl.Context([device])
    self._queue = cl.CommandQueue(self._context, device, properties=cl.command_queue_properties.PROFILING_ENABLE)
    self._kernels: dict[str, Any] = {}
    self._staging: dict[str, Any] = {}
    self._timer: OpenClProfilingTimer | None = None

  def close(self) -> None:
    """Termina lo pendiente y libera los staging (idempotente)."""
    if self._queue is None:
      return
    self._queue.finish()
    for buffer in self._staging.values():
      buffer.release()
    self._staging, self._kernels, self._queue = {}, {}, None

  # --- Compilación -----------------------------------------------------------------

  def _build_kernels(self) -> None:
    """Compila mosaic.cl con los -D compartidos; el build log completo va en el error."""
    cl = self._cl
    try:
      with warnings.catch_warnings(record=True) as compiler_output:
        program = cl.Program(self._context, load_kernel_source(OPENCL_SOURCE_NAME)).build(options=define_options())
    except cl.Error as error:
      raise BackendInitError(REASON_KERNEL_BUILD, str(error)) from error
    for message in compiler_output:
      logger.debug("salida del compilador OpenCL: %s", message.message)
    self._kernels = {name: cl.Kernel(program, name) for name in KERNEL_NAMES}

  # --- Memoria y transferencias ---------------------------------------------------------

  def _create_timer(self) -> StageTimer:
    """Profiling de los eventos de la cola."""
    self._timer = OpenClProfilingTimer()
    return self._timer

  def _alloc(self, nbytes: int) -> Any:
    """Reserva un buffer del dispositivo (al menos 1 byte)."""
    return self._cl.Buffer(self._context, self._cl.mem_flags.READ_WRITE, size=max(nbytes, 1))

  def _free(self, buffer: Any) -> None:
    """Libera un buffer del dispositivo."""
    buffer.release()

  def _available_matching_bytes(self, job: MosaicJob) -> int:
    """Fracción de la memoria (libre si es AMD, global si no) menos lo reservado."""
    reserved = sum(job_buffer_sizes(job).values())
    return opencl_available_bytes(
      self._device.global_mem_size, self._amd_free_bytes(), reserved, OPENCL_MEMORY_FRACTION
    )

  def _amd_free_bytes(self) -> int | None:
    """Memoria libre informada por la extensión de AMD, si existe."""
    if AMD_FREE_MEMORY_EXTENSION not in self._device.extensions:
      return None
    try:
      return int(self._device.get_info(self._cl.device_info.GLOBAL_FREE_MEMORY_AMD)[0]) * KIB
    except (self._cl.Error, IndexError, TypeError):
      return None

  def _max_alloc_bytes(self) -> int:
    """Reserva individual máxima del dispositivo (``MAX_MEM_ALLOC_SIZE``)."""
    return self._device.max_mem_alloc_size

  def _staging_buffer(self, key: str, nbytes: int) -> Any:
    """Buffer ``ALLOC_HOST_PTR`` reutilizable si el siguiente trabajo entra en él."""
    current = self._staging.get(key)
    if current is not None and current.size >= nbytes:
      return current
    if current is not None:
      current.release()
    flags = self._cl.mem_flags.READ_WRITE | self._cl.mem_flags.ALLOC_HOST_PTR
    self._staging[key] = self._cl.Buffer(self._context, flags, size=nbytes)
    return self._staging[key]

  def _map(self, buffer: Any, flags: int, nbytes: int) -> np.ndarray:
    """Mapea los primeros ``nbytes`` del staging en memoria del host (bloqueante)."""
    mapped, _ = self._cl.enqueue_map_buffer(self._queue, buffer, flags, 0, (nbytes,), np.uint8)
    return mapped

  def _copy_inputs(self, job: MosaicJob, timer: GpuStageTimer) -> None:
    """Escribe las entradas en el staging mapeado y encola las copias buffer → buffer."""
    start = time.perf_counter()
    total = sum(getattr(job, name).nbytes for name in INPUT_NAMES)
    staging = self._staging_buffer(INPUT_STAGING, total)
    mapped = self._map(staging, self._cl.map_flags.WRITE_INVALIDATE_REGION, total)
    placed = list(pack_inputs(mapped, job))
    mapped.base.release(queue=self._queue)
    timer.record_host(Stage.STAGING_H2D, elapsed_ms_since(start))
    timer.start(Stage.TRANSFER_H2D)
    for name, offset, nbytes in placed:
      self._timer.add(
        self._cl.enqueue_copy(self._queue, job.buffers[name], staging, byte_count=nbytes, src_offset=offset)
      )
    timer.stop(Stage.TRANSFER_H2D)

  def _output_staging(self, job: MosaicJob) -> Any:
    """Staging ``ALLOC_HOST_PTR`` para la imagen final."""
    return self._staging_buffer(OUTPUT_STAGING, int(np.prod(job.output_shape)))

  def _enqueue_image_copy(self, job: MosaicJob, staging: Any, timer: StageTimer) -> None:
    """Única copia D→H medida del trabajo: imagen → staging."""
    timer.start(Stage.TRANSFER_D2H)
    nbytes = int(np.prod(job.output_shape))
    self._timer.add(self._cl.enqueue_copy(self._queue, staging, job.buffers["image"], byte_count=nbytes))
    timer.stop(Stage.TRANSFER_D2H)

  def _read_staging(self, staging: Any, shape: tuple[int, ...]) -> np.ndarray:
    """Mapea el staging para lectura y copia la imagen a un array propio."""
    mapped = self._map(staging, self._cl.map_flags.READ, int(np.prod(shape)))
    image = mapped.reshape(shape).copy()
    mapped.base.release(queue=self._queue)
    return image

  def _read(self, buffer: Any, shape: tuple[int, ...], dtype: type) -> np.ndarray:
    """Lectura de validación en la misma cola, después de la medición."""
    out = np.empty(shape, dtype=dtype)
    self._cl.enqueue_copy(self._queue, out, buffer, is_blocking=True)
    return out

  # --- Lanzamientos y sincronización ------------------------------------------------------

  def _launch(self, name: str, grid: tuple[int, ...], block: tuple[int, ...], args: tuple) -> None:
    """Encola un kernel: global size = bloques × work-group (múltiplo exacto del local size)."""
    global_size = tuple(blocks * threads for blocks, threads in zip(grid, block, strict=True))
    self._timer.add(self._kernels[name](self._queue, global_size, block, *args))

  def _record_marker(self) -> Any:
    """Marcador en la cola (para el progreso diferido)."""
    return self._cl.enqueue_marker(self._queue)

  def _wait_marker(self, marker: Any) -> None:
    """Espera a que la cola alcance el marcador."""
    marker.wait()

  def _synchronize(self) -> None:
    """Espera a que termine todo lo encolado."""
    if self._queue is not None:
      self._queue.finish()

  def _is_out_of_memory(self, error: Exception) -> bool:
    """Falta de memoria informada por el driver (incluye pedir más que ``MAX_MEM_ALLOC_SIZE``)."""
    if isinstance(error, self._cl.MemoryError):
      return True
    codes = [getattr(self._cl.status_code, name, None) for name in OUT_OF_MEMORY_CODES]
    return isinstance(error, self._cl.Error) and error.code in codes
