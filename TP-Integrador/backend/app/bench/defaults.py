"""Valores por defecto del benchmark (design D1 y D2 del cambio 5).

``benchmark.py`` los usa como defaults de ``argparse``: así el script no tiene
números mágicos y ``make bench`` corre exactamente esta configuración.
"""

from app.backends.registry import CPU, CUDA, OPENCL
from app.core.constants import DEFAULT_ALPHA, DEFAULT_K, DEFAULT_SEED, DEFAULT_TILE_PX

# --- Grilla de tamaños y parámetros del trabajo ---------------------------------

DEFAULT_BACKENDS = (CUDA, OPENCL, CPU)
DEFAULT_N_VALUES = (100, 1_000, 5_000)
DEFAULT_M_VALUES = (1_000, 10_000, 40_000)
# 32 y no 64: con M = 40.000 la salida de 64 px pesa ~490 MB por backend (design D1).
BENCH_TILE_PX = DEFAULT_TILE_PX
BENCH_K = DEFAULT_K
BENCH_ALPHA = DEFAULT_ALPHA
BENCH_SEED = DEFAULT_SEED

# --- Medición ---------------------------------------------------------------------

DEFAULT_REPEATS = 3
# Por encima de esta estimación, la combinación de CPU se omite.
DEFAULT_MAX_CPU_SECONDS = 600.0
DEFAULT_OUT_DIR = "resultados"

# --- Datos sintéticos (design D2) --------------------------------------------------

# Razón cols/rows buscada para la grilla del objetivo.
TARGET_ASPECT_COLS = 4
TARGET_ASPECT_ROWS = 3
# Amplitud (en niveles de 8 bits) de la textura de ruido de cada tesela.
TILE_NOISE_AMPLITUDE = 12.0
# Teselas que se generan por bloque, para acotar los temporales float32.
TILE_CHUNK = 256
# Gaussianas de color que forman el objetivo y su ancho relativo al lado menor.
TARGET_BLOBS = 12
TARGET_BLOB_MIN_SIGMA = 0.08
TARGET_BLOB_MAX_SIGMA = 0.3
# Evita dividir por cero donde ninguna gaussiana tiene peso.
TARGET_WEIGHT_EPSILON = 1e-6

# --- Salidas ------------------------------------------------------------------------

CSV_NAME = "benchmark.csv"
PLOT_NAME = "benchmark.png"
MARKDOWN_NAME = "benchmark.md"
PLOT_DPI = 150
PLOT_SIZE_INCHES = (8.0, 5.5)
PLOT_GRID_ALPHA = 0.3
