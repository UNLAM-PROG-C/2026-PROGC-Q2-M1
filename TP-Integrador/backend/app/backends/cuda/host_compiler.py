"""Opciones de nvcc para encontrar el compilador de host.

nvcc compila el código de host (y preprocesa el de dispositivo) con el
compilador de C++ del sistema. En Linux usa ``gcc`` del PATH; en Windows
necesita ``cl.exe`` de Visual Studio, que normalmente **no** está en el PATH
fuera de un "Developer Command Prompt". Este módulo lo busca así:

1. si ``cl`` ya está en el PATH, no hace falta nada;
2. si está definida ``CUDA_HOST_COMPILER_DIR`` (ver ``env.example``), se usa;
3. si no, se pregunta a ``vswhere.exe`` por las instalaciones de Visual Studio
   con las herramientas de C++ y se toma el ``cl.exe`` x64 de versión más alta;
4. como último recurso se recorren las carpetas estándar de Visual Studio.

Además, ``CUDA_NVCC_OPTIONS`` permite agregar opciones a nvcc (por ejemplo
``-allow-unsupported-compiler`` si el Visual Studio es más nuevo que el CUDA
Toolkit).
"""

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

HOST_COMPILER_DIR_VAR = "CUDA_HOST_COMPILER_DIR"
EXTRA_NVCC_OPTIONS_VAR = "CUDA_NVCC_OPTIONS"
CL_RELATIVE_GLOB = "VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe"
VSWHERE_RELATIVE = Path("Microsoft Visual Studio/Installer/vswhere.exe")
VS_ROOT_NAME = "Microsoft Visual Studio"
# vswhere: instalaciones (incluidas Build Tools) que tienen el compilador x64.
VSWHERE_ARGS = (
  "-all",
  "-products",
  "*",
  "-requires",
  "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
  "-property",
  "installationPath",
)
VSWHERE_TIMEOUT_SECONDS = 30
WINDOWS = "win32"


class HostCompilerNotFoundError(RuntimeError):
  """No se encontró ``cl.exe`` para que nvcc compile en Windows."""


def _program_files_dirs() -> list[Path]:
  """Carpetas "Program Files" de 64 y 32 bits."""
  names = ("ProgramFiles", "ProgramFiles(x86)")
  return [Path(os.environ[name]) for name in names if os.environ.get(name)]


def _vswhere_installations() -> list[Path]:
  """Instalaciones de Visual Studio con herramientas de C++ según vswhere (puede ser vacía)."""
  for base in _program_files_dirs():
    vswhere = base / VSWHERE_RELATIVE
    if vswhere.is_file():
      result = subprocess.run(
        [str(vswhere), *VSWHERE_ARGS], capture_output=True, text=True, timeout=VSWHERE_TIMEOUT_SECONDS, check=False
      )
      return [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
  return []


def _standard_installations() -> list[Path]:
  """Instalaciones en las carpetas estándar (``<Program Files>/Microsoft Visual Studio/<versión>/<edición>``)."""
  return [path for base in _program_files_dirs() for path in (base / VS_ROOT_NAME).glob("*/*") if path.is_dir()]


def _msvc_version(cl_path: Path) -> tuple[int, ...]:
  """Versión de MSVC a partir de la ruta ``.../MSVC/<versión>/bin/...``."""
  version = cl_path.parents[3].name
  return tuple(int(part) for part in version.split(".") if part.isdigit())


def find_cl_dir() -> Path | None:
  """Carpeta del ``cl.exe`` x64 de versión más alta, o ``None`` si no hay."""
  candidates = [
    cl for install in (*_vswhere_installations(), *_standard_installations()) for cl in install.glob(CL_RELATIVE_GLOB)
  ]
  if not candidates:
    return None
  return max(candidates, key=_msvc_version).parent


def host_compiler_options() -> list[str]:
  """``["-ccbin", carpeta]`` si nvcc necesita que le indiquen dónde está ``cl.exe``."""
  if sys.platform != WINDOWS or shutil.which("cl"):
    return []
  configured = os.environ.get(HOST_COMPILER_DIR_VAR, "").strip()
  found = Path(configured) if configured else find_cl_dir()
  if found is None:
    raise HostCompilerNotFoundError(
      f"no se encontró cl.exe de Visual Studio; instalar las herramientas de C++ o definir {HOST_COMPILER_DIR_VAR}"
    )
  return ["-ccbin", str(found)]


def extra_nvcc_options() -> list[str]:
  """Opciones adicionales de nvcc desde ``CUDA_NVCC_OPTIONS``."""
  return shlex.split(os.environ.get(EXTRA_NVCC_OPTIONS_VAR, ""))
