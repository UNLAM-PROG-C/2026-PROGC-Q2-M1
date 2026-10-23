"""Única fuente de verdad de las constantes del algoritmo de fotomosaico.

Los backends (CPU, y en el cambio 2 CUDA y OpenCL) toman estos valores de acá:
ningún otro módulo repite estos literales.
"""

# --- Geometría de las teselas y de los descriptores --------------------------

# Lado de cada tesela normalizada por la etapa de carga (tiles_src).
TILE_SRC_PX = 128
# Canales de color (RGB).
RGB_CHANNELS = 3
# Lado de la miniatura que forma el descriptor (8×8 posiciones Lab).
DESC_GRID = 8
# Lado del bloque de la tesela fuente que se promedia por posición (128 / 8).
DESC_BLOCK_PX = TILE_SRC_PX // DESC_GRID
# Largo del descriptor: 8·8 posiciones × 3 canales = 192 floats.
DESC_DIM = DESC_GRID * DESC_GRID * RGB_CHANNELS
# Píxeles de target_src por celda (cada celda es un bloque de 8×8).
CELL_PX = DESC_GRID

# --- Parámetros del trabajo ---------------------------------------------------

# Lados permitidos de la tesela en la imagen final.
ALLOWED_TILE_PX = (16, 32, 64)
DEFAULT_TILE_PX = 32
# Rango de columnas de la grilla (cols).
MIN_COLS = 1
MAX_COLS = 400
# Rango de candidatos por celda (k).
MIN_K = 1
MAX_K = 16
DEFAULT_K = 5
# Rango de la mezcla con el objetivo (alpha).
MIN_ALPHA = 0.0
MAX_ALPHA = 1.0
DEFAULT_ALPHA = 1.0
# Semilla por defecto del generador de choice.
DEFAULT_SEED = 0
MIN_SEED = 0

# --- Representación de píxeles -------------------------------------------------

# Valor máximo de un canal de 8 bits.
MAX_CHANNEL_VALUE = 255
# Sumando para redondear al entero más cercano (mitad hacia arriba).
ROUND_HALF = 0.5

# --- Backend CPU ----------------------------------------------------------------

# Bytes de un float32.
FLOAT32_BYTES = 4
# Presupuesto de memoria de la matriz parcial de distancias [m_chunk, N].
CPU_DISTANCE_BUDGET_BYTES = 64 * 1024 * 1024

# --- Carga de imágenes ------------------------------------------------------------

# Formatos que acepta la carga (nombres de formato de Pillow).
SUPPORTED_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})

# --- Equivalencia entre backends (design D3) --------------------------------------

# Diferencia absoluta máxima aceptada entre descriptores Lab de dos backends.
EQUIVALENCE_LAB_TOLERANCE = 1e-2
# Diferencia relativa máxima aceptada entre topk_dist de dos backends.
EQUIVALENCE_DIST_RELATIVE_TOLERANCE = 1e-4
# Fracción mínima de celdas cuyo topk_idx debe coincidir con el de CPU.
MIN_MATCHING_CELLS_RATIO = 0.99
