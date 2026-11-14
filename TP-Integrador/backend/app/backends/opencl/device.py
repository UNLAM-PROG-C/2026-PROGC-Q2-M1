"""Selección del dispositivo OpenCL (spec backend-opencl, design D7 del cambio 2).

Funciones puras sobre objetos con la forma de los de PyOpenCL (``platform.get_devices()``,
``device.type``, ``device.vendor``, ``device.name``), así se prueban con plataformas falsas.

Regla: solo GPUs, de todas las plataformas; primero las de vendor AMD y, entre las
restantes, la primera en orden de plataforma y dispositivo. Opcionalmente, la
variable ``OPENCL_DEVICE`` (ver ``env.example``) restringe la búsqueda a las GPUs
cuyo nombre o vendor la contienen, para elegir otra placa en máquinas con varias
(por ejemplo, comparar CUDA y OpenCL sobre la misma NVIDIA cuando también hay
una GPU integrada AMD).
"""

import os
from collections.abc import Iterable
from typing import Any

AMD_VENDOR_MARKERS = ("AMD", "Advanced Micro Devices")
DEVICE_FILTER_VAR = "OPENCL_DEVICE"


def is_amd(device: Any) -> bool:
  """Indica si el vendor del dispositivo es AMD."""
  return any(marker in device.vendor for marker in AMD_VENDOR_MARKERS)


def _platform_devices(platform: Any, lookup_errors: tuple[type[Exception], ...]) -> list[Any]:
  """Dispositivos de una plataforma; una plataforma sin dispositivos devuelve lista vacía."""
  try:
    return list(platform.get_devices())
  except lookup_errors:
    return []


def gpu_devices(platforms: Iterable[Any], gpu_type: int, lookup_errors: tuple[type[Exception], ...] = ()) -> list[Any]:
  """GPUs de todas las plataformas, en orden de plataforma y dispositivo."""
  return [
    device for platform in platforms for device in _platform_devices(platform, lookup_errors) if device.type & gpu_type
  ]


def _matches(device: Any, name_filter: str) -> bool:
  """El nombre o el vendor del dispositivo contienen el filtro (sin distinguir mayúsculas)."""
  needle = name_filter.lower()
  return needle in device.name.lower() or needle in device.vendor.lower()


def select_gpu(
  platforms: Iterable[Any],
  gpu_type: int,
  lookup_errors: tuple[type[Exception], ...] = (),
  name_filter: str | None = None,
) -> Any | None:
  """GPU a usar: AMD primero, si no la primera; ``None`` si no hay ninguna."""
  candidates = gpu_devices(platforms, gpu_type, lookup_errors)
  if name_filter:
    candidates = [device for device in candidates if _matches(device, name_filter)]
  amd_first = sorted(candidates, key=lambda device: not is_amd(device))
  return amd_first[0] if amd_first else None


def display_name(device: Any, lookup_errors: tuple[type[Exception], ...] = ()) -> str:
  """Nombre comercial: en AMD, ``board_name_amd`` ("AMD Radeon...") en lugar del código (gfx…)."""
  name = device.name.strip()
  if not is_amd(device):
    return name
  try:
    return f"{device.board_name_amd.strip()} ({name})"
  except (*lookup_errors, AttributeError):
    return name


def configured_filter() -> str | None:
  """Filtro de ``OPENCL_DEVICE``, o ``None`` si no está definido."""
  return os.environ.get(DEVICE_FILTER_VAR, "").strip() or None
