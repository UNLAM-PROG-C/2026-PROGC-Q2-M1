"""Conversión sRGB → CIELAB contra valores de referencia publicados."""

import numpy as np
import pytest

from app.backends.cpu import stages
from app.core.color import srgb_to_lab_reference

# Valores de referencia (D65, 2°) de la conversión estándar sRGB → CIELAB.
REFERENCE_COLORS = [
  ((255, 255, 255), (100.0, 0.0, 0.0), 0.01),
  ((0, 0, 0), (0.0, 0.0, 0.0), 0.01),
  ((255, 0, 0), (53.24, 80.09, 67.20), 0.05),
  ((0, 255, 0), (87.73, -86.18, 83.18), 0.05),
  ((0, 0, 255), (32.30, 79.19, -107.86), 0.05),
  ((128, 128, 128), (53.59, 0.0, 0.0), 0.05),
]


@pytest.mark.parametrize(("rgb", "expected", "tolerance"), REFERENCE_COLORS)
def test_reference_conversion_matches_published_values(rgb, expected, tolerance):
  np.testing.assert_allclose(srgb_to_lab_reference(np.array(rgb)), expected, atol=tolerance)


@pytest.mark.parametrize(("rgb", "expected", "tolerance"), REFERENCE_COLORS)
def test_float32_conversion_matches_published_values(rgb, expected, tolerance):
  lab = stages.srgb_to_lab(np.uint8(rgb[0]), np.uint8(rgb[1]), np.uint8(rgb[2]))
  np.testing.assert_allclose(lab, expected, atol=tolerance)


def test_float32_conversion_does_not_promote_to_float64():
  stages.srgb_to_lab(np.uint8(1), np.uint8(2), np.uint8(3))
  return_types = {str(signature.return_type) for signature in stages.srgb_to_lab.nopython_signatures}
  assert return_types == {"UniTuple(float32 x 3)"}
