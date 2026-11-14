"""Constantes de la conversión sRGB → CIELAB y una conversión de referencia.

Las constantes float64 de este módulo son la definición del algoritmo; los
backends usan las copias float32 (sufijo ``_F32``). La función
``srgb_to_lab_reference`` calcula en float64 con NumPy y sirve solo para los
tests: no es parte de ningún backend.
"""

import numpy as np

from app.core.constants import MAX_CHANNEL_VALUE

# Matriz sRGB lineal → XYZ (iluminante D65, IEC 61966-2-1).
SRGB_TO_XYZ = np.array(
  [
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041],
  ],
  dtype=np.float64,
)
# Blanco de referencia D65 (X, Y, Z).
D65_WHITE = np.array([0.95047, 1.0, 1.08883], dtype=np.float64)

# Curva gamma de sRGB: tramo lineal hasta el umbral y potencia después.
SRGB_LINEAR_THRESHOLD = 0.04045
SRGB_LINEAR_SLOPE = 12.92
SRGB_GAMMA_OFFSET = 0.055
SRGB_GAMMA_SCALE = 1.055
SRGB_GAMMA_EXPONENT = 2.4

# Función f(t) de CIELAB: raíz cúbica sobre el umbral y recta debajo.
LAB_DELTA = 6.0 / 29.0
LAB_EPSILON = LAB_DELTA**3
LAB_LINEAR_DIVISOR = 3.0 * LAB_DELTA**2
LAB_LINEAR_OFFSET = 4.0 / 29.0

# Coeficientes de L, a y b.
LAB_L_SCALE = 116.0
LAB_L_OFFSET = 16.0
LAB_A_SCALE = 500.0
LAB_B_SCALE = 200.0

# Copias float32 para los backends (evitan la promoción silenciosa a float64).
CHANNEL_MAX_F32 = np.float32(MAX_CHANNEL_VALUE)
SRGB_TO_XYZ_F32 = SRGB_TO_XYZ.astype(np.float32)
D65_WHITE_F32 = D65_WHITE.astype(np.float32)
SRGB_LINEAR_THRESHOLD_F32 = np.float32(SRGB_LINEAR_THRESHOLD)
SRGB_LINEAR_SLOPE_F32 = np.float32(SRGB_LINEAR_SLOPE)
SRGB_GAMMA_OFFSET_F32 = np.float32(SRGB_GAMMA_OFFSET)
SRGB_GAMMA_SCALE_F32 = np.float32(SRGB_GAMMA_SCALE)
SRGB_GAMMA_EXPONENT_F32 = np.float32(SRGB_GAMMA_EXPONENT)
LAB_EPSILON_F32 = np.float32(LAB_EPSILON)
LAB_LINEAR_DIVISOR_F32 = np.float32(LAB_LINEAR_DIVISOR)
LAB_LINEAR_OFFSET_F32 = np.float32(LAB_LINEAR_OFFSET)
LAB_L_SCALE_F32 = np.float32(LAB_L_SCALE)
LAB_L_OFFSET_F32 = np.float32(LAB_L_OFFSET)
LAB_A_SCALE_F32 = np.float32(LAB_A_SCALE)
LAB_B_SCALE_F32 = np.float32(LAB_B_SCALE)


def _linearize_reference(channel: np.ndarray) -> np.ndarray:
  """Aplica la inversa de la curva gamma de sRGB a valores en [0, 1]."""
  linear = channel / SRGB_LINEAR_SLOPE
  curved = ((channel + SRGB_GAMMA_OFFSET) / SRGB_GAMMA_SCALE) ** SRGB_GAMMA_EXPONENT
  return np.where(channel <= SRGB_LINEAR_THRESHOLD, linear, curved)


def _lab_f_reference(t: np.ndarray) -> np.ndarray:
  """Función f(t) de CIELAB."""
  linear = t / LAB_LINEAR_DIVISOR + LAB_LINEAR_OFFSET
  return np.where(t > LAB_EPSILON, np.cbrt(t), linear)


def srgb_to_lab_reference(rgb: np.ndarray) -> np.ndarray:
  """Convierte colores sRGB en [0, 255] (último eje = canal) a Lab en float64."""
  normalized = np.asarray(rgb, dtype=np.float64) / MAX_CHANNEL_VALUE
  xyz = _linearize_reference(normalized) @ SRGB_TO_XYZ.T
  fx, fy, fz = np.moveaxis(_lab_f_reference(xyz / D65_WHITE), -1, 0)
  lightness = LAB_L_SCALE * fy - LAB_L_OFFSET
  return np.stack([lightness, LAB_A_SCALE * (fx - fy), LAB_B_SCALE * (fy - fz)], axis=-1)
