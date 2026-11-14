"""Partes de GPU que no necesitan GPU: constantes de kernels, paridad, bloques y progreso."""

import re

import numpy as np
import pytest

from app.backends.gpu_base import KERNEL_NAMES, DeferredProgressReporter, ceil_div, matching_chunk_rows
from app.backends.kernel_build import (
  CUDA_SOURCE_NAME,
  FLOAT_DEFINES,
  INT_DEFINES,
  KERNELS_DIR,
  OPENCL_SOURCE_NAME,
  define_options,
  kernel_defines,
  load_kernel_source,
)
from app.core import color
from app.core.backend import OutOfMemoryError
from app.core.constants import FLOAT32_BYTES, MATMUL_TILE
from app.core.result import Stage

N_TILES = 5000
ROW_BYTES = N_TILES * FLOAT32_BYTES
# Calificadores propios de cada API que se quitan para comparar firmas.
API_QUALIFIERS = re.compile(r"\b(__global__|__kernel|__global|unsigned char|uchar)\b")
# "void [__launch_bounds__(...)] nombre(parámetros)"; solo se comparan los kernels.
KERNEL_SIGNATURE = re.compile(r"void\s+(?:__launch_bounds__\([^)]*\)\s+)?(\w+)\(([^)]*)\)")
# Un literal numérico de más de un dígito fuera de comentarios sería un número mágico.
MULTI_DIGIT_LITERAL = re.compile(r"(?<![\w.])\d{2,}(?![\w.])")


# --- Constantes compartidas (task 1.2) ---------------------------------------------------


def parse_defines() -> dict[str, str]:
  return dict(option[2:].split("=", 1) for option in define_options())


def test_int_defines_match_python_constants():
  defines = parse_defines()
  for name, value in INT_DEFINES.items():
    assert int(defines[name]) == value


def test_float_defines_are_the_exact_float32_constants():
  defines = parse_defines()
  for name, value in FLOAT_DEFINES.items():
    assert defines[name].endswith("f")
    assert np.float32(defines[name][:-1]) == np.float32(value)


def test_color_matrix_and_white_point_defines():
  defines = parse_defines()
  for row in range(3):
    assert np.float32(defines[f"WHITE_{'XYZ'[row]}"][:-1]) == color.D65_WHITE_F32[row]
    for col in range(3):
      assert np.float32(defines[f"SRGB_TO_XYZ_{row}{col}"][:-1]) == color.SRGB_TO_XYZ_F32[row, col]


# --- Paridad de kernels (task 2.2) ---------------------------------------------------------


def signatures(file_name: str) -> dict[str, list[str]]:
  source = load_kernel_source(file_name)
  found = {}
  for name, params in KERNEL_SIGNATURE.findall(source):
    if name not in KERNEL_NAMES:
      continue
    normalized = API_QUALIFIERS.sub("", " ".join(params.split()))
    found[name] = [" ".join(param.split()) for param in normalized.split(",")]
  return found


def test_both_files_define_the_same_kernels_with_the_same_parameters():
  cuda, opencl = signatures(CUDA_SOURCE_NAME), signatures(OPENCL_SOURCE_NAME)
  assert set(cuda) == set(opencl) == set(KERNEL_NAMES)
  assert cuda == opencl


def code_without_comments(file_name: str) -> str:
  source = (KERNELS_DIR / file_name).read_text(encoding="utf-8")
  return "\n".join(line.split("//", 1)[0] for line in source.splitlines())


@pytest.mark.parametrize("file_name", [CUDA_SOURCE_NAME, OPENCL_SOURCE_NAME])
def test_kernels_have_no_business_literals_and_use_every_define(file_name):
  code = code_without_comments(file_name)
  assert MULTI_DIGIT_LITERAL.findall(code) == []
  unused = [name for name in kernel_defines() if not re.search(rf"\b{name}\b", code)]
  assert unused == []


# --- Bloques del matching (design D6) -------------------------------------------------------


def test_chunk_fits_available_memory_in_multiples_of_the_tile():
  rows = matching_chunk_rows(1000 * ROW_BYTES, N_TILES, 40_000)
  assert rows <= 1000 and rows % MATMUL_TILE == 0 and rows > 1000 - MATMUL_TILE


def test_chunk_is_bounded_by_the_number_of_cells():
  assert matching_chunk_rows(10**12, N_TILES, 37) == 37


def test_chunk_fails_when_not_even_a_minimum_block_fits():
  with pytest.raises(OutOfMemoryError, match="memoria insuficiente"):
    matching_chunk_rows(MATMUL_TILE * ROW_BYTES - 1, N_TILES, 40_000)


def test_ceil_div_rounds_up():
  assert (ceil_div(32, 16), ceil_div(33, 16), ceil_div(1, 256)) == (2, 3, 1)


# --- Progreso diferido (design D4) -------------------------------------------------------------


def test_deferred_progress_waits_markers_in_order_before_forwarding():
  log = []
  markers = iter(range(10))
  reporter = DeferredProgressReporter(
    lambda stage, fraction: log.append(("aviso", fraction)), lambda: next(markers), lambda m: log.append(("espera", m))
  )
  reporter.report(Stage.MATCHING, 0.5)
  reporter.report(Stage.MATCHING, 1.0)
  assert log == []
  reporter.drain()
  assert log == [("espera", 0), ("aviso", 0.5), ("espera", 1), ("aviso", 1.0)]


def test_deferred_progress_without_observer_records_no_markers():
  reporter = DeferredProgressReporter(None, lambda: pytest.fail("no debería registrar marcadores"), lambda m: None)
  reporter.report(Stage.MATCHING, 1.0)
  reporter.drain()
