// Kernels OpenCL del fotomosaico (cambio 2, design D2/D3).
//
// Gemelo de kernels/mosaic.cu: mismos kernels, mismos argumentos en el mismo
// orden y el mismo mapeo hilo -> dato. Solo cambian los calificadores de cada
// API (__kernel / __global__, __local / __shared__, barrier / __syncthreads) y
// uchar en lugar de unsigned char. Equivalencias de índices:
//   get_group_id(d) = blockIdx.{x,y}, get_local_id(d) = threadIdx.{x,y},
//   get_global_id(d) = blockIdx * blockDim + threadIdx.
// El global size se redondea hacia arriba al múltiplo del work-group y cada
// kernel descarta los hilos sobrantes con un if, igual que en CUDA.
//
// Cada kernel declara con reqd_work_group_size el tamaño de work-group con el
// que se lanza (la misma constante que usa el host y que el __launch_bounds__
// de CUDA): si el host lanzara con otro tamaño, el driver rechaza el lanzamiento.
//
// Ninguna constante del algoritmo está escrita acá: llegan como -DNOMBRE=valor
// desde app/backends/kernel_build.py (misma fuente que el CPU).

// --- Funciones auxiliares (inline en cada hilo) ------------------------------

// Inversa de la curva gamma de sRGB para un canal en [0, 255].
float linearize(float channel)
{
  float value = channel / CHANNEL_MAX;
  if (value <= SRGB_LINEAR_THRESHOLD)
  {
    return value / SRGB_LINEAR_SLOPE;
  }
  return pow((value + SRGB_GAMMA_OFFSET) / SRGB_GAMMA_SCALE, SRGB_GAMMA_EXPONENT);
}

// Función f(t) de CIELAB.
float lab_f(float t)
{
  if (t > LAB_EPSILON)
  {
    return cbrt(t);
  }
  return t / LAB_LINEAR_DIVISOR + LAB_LINEAR_OFFSET;
}

// Convierte un color sRGB (canales en [0, 255]) a Lab y lo escribe en out[0..2].
void write_lab(float red, float green, float blue, __global float *out)
{
  float r = linearize(red);
  float g = linearize(green);
  float b = linearize(blue);
  float fx = lab_f((SRGB_TO_XYZ_00 * r + SRGB_TO_XYZ_01 * g + SRGB_TO_XYZ_02 * b) / WHITE_X);
  float fy = lab_f((SRGB_TO_XYZ_10 * r + SRGB_TO_XYZ_11 * g + SRGB_TO_XYZ_12 * b) / WHITE_Y);
  float fz = lab_f((SRGB_TO_XYZ_20 * r + SRGB_TO_XYZ_21 * g + SRGB_TO_XYZ_22 * b) / WHITE_Z);
  out[0] = LAB_L_SCALE * fy - LAB_L_OFFSET;
  out[1] = LAB_A_SCALE * (fx - fy);
  out[2] = LAB_B_SCALE * (fy - fz);
}

// Orden total (distancia, índice): ante igual distancia gana el índice menor.
bool precedes(float dist_a, int idx_a, float dist_b, int idx_b)
{
  return dist_a < dist_b || (dist_a == dist_b && idx_a < idx_b);
}

// --- Etapa 1: preparación de teselas ------------------------------------------

// Inicio de la tesela `tile` en tiles_src [N, TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS].
__global const uchar *tile_source(__global const uchar *tiles_src, int tile)
{
  return tiles_src + (size_t)tile * TILE_SRC_PX * TILE_SRC_PX * RGB_CHANNELS;
}

// Promedio entero redondeado de un canal en el bloque factor×factor que empieza en (y0, x0).
uchar block_mean_rounded(__global const uchar *src, int y0, int x0, int channel, int factor)
{
  int area = factor * factor;
  int total = 0;
  for (int dy = 0; dy < factor; ++dy)
  {
    for (int dx = 0; dx < factor; ++dx)
    {
      total += src[((y0 + dy) * TILE_SRC_PX + x0 + dx) * RGB_CHANNELS + channel];
    }
  }
  return (uchar)((total + area / 2) / area);
}

// Promedio float de un canal en el bloque DESC_BLOCK_PX×DESC_BLOCK_PX que empieza en (y0, x0).
float block_mean_srgb(__global const uchar *src, int y0, int x0, int channel)
{
  int total = 0;
  for (int dy = 0; dy < DESC_BLOCK_PX; ++dy)
  {
    for (int dx = 0; dx < DESC_BLOCK_PX; ++dx)
    {
      total += src[((y0 + dy) * TILE_SRC_PX + x0 + dx) * RGB_CHANNELS + channel];
    }
  }
  return total / (float)(DESC_BLOCK_PX * DESC_BLOCK_PX);
}

// resize_tiles: un hilo por píxel de salida (3 canales) de tiles_px.
// Índice: gid = get_global_id(0) -> (tile, y, x) con
// tile = gid / tile_px², y = (gid / tile_px) % tile_px, x = gid % tile_px.
// Cada hilo promedia con redondeo entero el bloque f×f de la tesela fuente,
// f = TILE_SRC_PX / tile_px. No usa memoria local.
__kernel __attribute__((reqd_work_group_size(BLOCK_1D, 1, 1))) void resize_tiles(__global const uchar *tiles_src, __global uchar *tiles_px, int n_tiles, int tile_px)
{
  int gid = get_global_id(0);
  if (gid >= n_tiles * tile_px * tile_px)
  {
    return;
  }
  int tile = gid / (tile_px * tile_px);
  int y = (gid / tile_px) % tile_px;
  int x = gid % tile_px;
  int factor = TILE_SRC_PX / tile_px;
  __global const uchar *src = tile_source(tiles_src, tile);
  for (int channel = 0; channel < RGB_CHANNELS; ++channel)
  {
    tiles_px[(size_t)gid * RGB_CHANNELS + channel] = block_mean_rounded(src, y * factor, x * factor, channel, factor);
  }
}

// tile_descriptors: un hilo por (tile, cy, cx) de la miniatura DESC_GRID×DESC_GRID.
// Índice: gid -> tile = gid / DESC_GRID², pos = gid % DESC_GRID² = cy * DESC_GRID + cx.
// Promedia en sRGB el bloque DESC_BLOCK_PX×DESC_BLOCK_PX de la fuente, lo pasa a Lab y
// escribe 3 floats en tile_desc[tile * DESC_DIM + pos * 3]. No usa memoria local.
__kernel __attribute__((reqd_work_group_size(BLOCK_1D, 1, 1))) void tile_descriptors(__global const uchar *tiles_src, __global float *tile_desc, int n_tiles)
{
  int gid = get_global_id(0);
  if (gid >= n_tiles * DESC_GRID * DESC_GRID)
  {
    return;
  }
  int tile = gid / (DESC_GRID * DESC_GRID);
  int pos = gid % (DESC_GRID * DESC_GRID);
  int y0 = (pos / DESC_GRID) * DESC_BLOCK_PX;
  int x0 = (pos % DESC_GRID) * DESC_BLOCK_PX;
  __global const uchar *src = tile_source(tiles_src, tile);
  float red = block_mean_srgb(src, y0, x0, 0);
  float green = block_mean_srgb(src, y0, x0, 1);
  float blue = block_mean_srgb(src, y0, x0, 2);
  write_lab(red, green, blue, tile_desc + (size_t)gid * RGB_CHANNELS);
}

// --- Etapa 2: descriptores del objetivo ---------------------------------------

// cell_descriptors: un hilo por (cell, py, px), un píxel del bloque CELL_PX×CELL_PX de una celda.
// Índice: gid -> cell = gid / CELL_PX², pos = gid % CELL_PX² = py * CELL_PX + px; la celda
// está en la fila cell / cols y la columna cell % cols. Escribe 3 floats en
// cell_desc[cell * DESC_DIM + pos * 3]. No usa memoria local.
__kernel __attribute__((reqd_work_group_size(BLOCK_1D, 1, 1))) void cell_descriptors(__global const uchar *target_src, __global float *cell_desc, int rows, int cols)
{
  int gid = get_global_id(0);
  if (gid >= rows * cols * CELL_PX * CELL_PX)
  {
    return;
  }
  int cell = gid / (CELL_PX * CELL_PX);
  int pos = gid % (CELL_PX * CELL_PX);
  int y = (cell / cols) * CELL_PX + pos / CELL_PX;
  int x = (cell % cols) * CELL_PX + pos % CELL_PX;
  __global const uchar *pixel = target_src + ((size_t)y * cols * CELL_PX + x) * RGB_CHANNELS;
  write_lab(pixel[0], pixel[1], pixel[2], cell_desc + (size_t)gid * RGB_CHANNELS);
}

// sq_norms: un hilo por vector de DESC_DIM floats (se lanza para teselas y para celdas).
// Índice: gid = número de vector. Suma de cuadrados en orden k = 0..DESC_DIM-1.
__kernel __attribute__((reqd_work_group_size(BLOCK_1D, 1, 1))) void sq_norms(__global const float *desc, __global float *norms, int n_vectors)
{
  int gid = get_global_id(0);
  if (gid >= n_vectors)
  {
    return;
  }
  __global const float *row = desc + (size_t)gid * DESC_DIM;
  float total = 0.0f;
  for (int d = 0; d < DESC_DIM; ++d)
  {
    total += row[d] * row[d];
  }
  norms[gid] = total;
}

// --- Etapa 3: matching -----------------------------------------------------------

// Producto escalar de una fila de a_tile con una de b_tile (un paso del tiling).
float tile_dot(__local const float *a_row, __local const float *b_row)
{
  float acc = 0.0f;
  for (int i = 0; i < MATMUL_TILE; ++i)
  {
    acc += a_row[i] * b_row[i];
  }
  return acc;
}

// distances_tiled: work-group MATMUL_TILE×MATMUL_TILE, un hilo por elemento dist[r, c] del bloque
// de celdas, con r = get_group_id(1) * MATMUL_TILE + get_local_id(1) (fila del chunk, celda
// row_offset + r) y c = get_group_id(0) * MATMUL_TILE + get_local_id(0) (tesela).
// Memoria local, en DESC_DIM / MATMUL_TILE pasos:
//   a_tile[ty][tx] = cell_desc[row_offset + fila ty del bloque][paso * MATMUL_TILE + tx]
//   b_tile[ty][tx] = tile_desc[tesela ty del bloque][paso * MATMUL_TILE + tx]
// b_tile tiene una columna de padding (MATMUL_TILE + 1): al leer b_tile[tx][d], los hilos de
// un warp/wavefront caen en bancos distintos. Los hilos fuera de rango cargan 0 y no
// escriben, pero participan de las barreras. Resultado: (‖c‖² + ‖t‖²) − 2·c·t.
__kernel __attribute__((reqd_work_group_size(MATMUL_TILE, MATMUL_TILE, 1))) void distances_tiled(__global const float *cell_desc, __global const float *tile_desc,
                                                                                                 __global const float *cell_norms, __global const float *tile_norms,
                                                                                                 __global float *dist, int row_offset, int m_chunk, int n_tiles)
{
  __local float a_tile[MATMUL_TILE][MATMUL_TILE];
  __local float b_tile[MATMUL_TILE][MATMUL_TILE + 1];
  int tx = get_local_id(0);
  int ty = get_local_id(1);
  int r = get_group_id(1) * MATMUL_TILE + ty;
  int c = get_group_id(0) * MATMUL_TILE + tx;
  int load_tile = get_group_id(0) * MATMUL_TILE + ty;
  float acc = 0.0f;
  for (int step = 0; step < DESC_DIM / MATMUL_TILE; ++step)
  {
    int d = step * MATMUL_TILE + tx;
    a_tile[ty][tx] = r < m_chunk ? cell_desc[(size_t)(row_offset + r) * DESC_DIM + d] : 0.0f;
    b_tile[ty][tx] = load_tile < n_tiles ? tile_desc[(size_t)load_tile * DESC_DIM + d] : 0.0f;
    barrier(CLK_LOCAL_MEM_FENCE);
    acc += tile_dot(a_tile[ty], b_tile[tx]);
    barrier(CLK_LOCAL_MEM_FENCE);
  }
  if (r < m_chunk && c < n_tiles)
  {
    dist[(size_t)r * n_tiles + c] = (cell_norms[row_offset + r] + tile_norms[c]) - 2.0f * acc;
  }
}

// Inserta (dist, idx) en la lista ordenada de k elementos en registros. El bucle se desenrolla
// con índices constantes (así la lista vive en registros): en cada posición se queda el menor
// de los dos y el mayor sigue hacia el final; el último se descarta.
void insert_sorted(float *best_dist, int *best_idx, float dist, int idx, int k)
{
#pragma unroll
  for (int i = 0; i < MAX_K; ++i)
  {
    if (i < k && precedes(dist, idx, best_dist[i], best_idx[i]))
    {
      float swap_dist = best_dist[i];
      int swap_idx = best_idx[i];
      best_dist[i] = dist;
      best_idx[i] = idx;
      dist = swap_dist;
      idx = swap_idx;
    }
  }
}

// Combina las listas ordenadas (de k elementos) de los hilos `self` y `other` en memoria
// local y deja en la de `self` las k menores. Como se toman k de 2k, ninguna lista se
// agota antes de terminar.
void merge_lists(__local float *s_dist, __local int *s_idx, int self, int other, int k)
{
  float out_dist[MAX_K];
  int out_idx[MAX_K];
  int a = self * MAX_K;
  int b = other * MAX_K;
#pragma unroll
  for (int i = 0; i < MAX_K; ++i)
  {
    if (i < k)
    {
      bool take_a = precedes(s_dist[a], s_idx[a], s_dist[b], s_idx[b]);
      int from = take_a ? a++ : b++;
      out_dist[i] = s_dist[from];
      out_idx[i] = s_idx[from];
    }
  }
#pragma unroll
  for (int i = 0; i < MAX_K; ++i)
  {
    if (i < k)
    {
      s_dist[self * MAX_K + i] = out_dist[i];
      s_idx[self * MAX_K + i] = out_idx[i];
    }
  }
}

// Recorre la porción intercalada de la fila que le toca al hilo t (c = t, t + TOPK_THREADS, ...)
// y deja su top-k ordenado en best_dist/best_idx (registros). Si ve menos de k columnas, la
// lista queda con relleno (+inf, INT_MAX), que siempre pierde.
void scan_row(__global const float *row, int n_tiles, int t, int k, float *best_dist, int *best_idx)
{
#pragma unroll
  for (int i = 0; i < MAX_K; ++i)
  {
    best_dist[i] = INFINITY;
    best_idx[i] = INT_MAX;
  }
  for (int c = t; c < n_tiles; c += TOPK_THREADS)
  {
    insert_sorted(best_dist, best_idx, row[c], c, k);
  }
}

// Vuelca la lista del hilo t a memoria local y combina las listas en árbol: en cada ronda
// el hilo t < stride absorbe la lista de t + stride. Al final, la lista 0 es el top-k de la fila.
void merge_tree(__local float *s_dist, __local int *s_idx, const float *best_dist, const int *best_idx, int t, int k)
{
#pragma unroll
  for (int i = 0; i < MAX_K; ++i)
  {
    s_dist[t * MAX_K + i] = best_dist[i];
    s_idx[t * MAX_K + i] = best_idx[i];
  }
  barrier(CLK_LOCAL_MEM_FENCE);
  for (int stride = TOPK_THREADS / 2; stride > 0; stride /= 2)
  {
    if (t < stride)
    {
      merge_lists(s_dist, s_idx, t, t + stride, k);
    }
    barrier(CLK_LOCAL_MEM_FENCE);
  }
}

// topk_rows: un work-group de TOPK_THREADS hilos por fila r = get_group_id(0) del chunk.
// El hilo t recorre c = t, t + TOPK_THREADS, ... (accesos coalescidos) con su top-k en
// registros; si ve menos de k columnas, su lista queda con relleno (+inf, INT_MAX), que
// siempre pierde. Luego vuelca su lista a memoria local
// (TOPK_THREADS·MAX_K·(4 + 4) B = 16 KiB) y se combinan en árbol: log2(TOPK_THREADS)
// rondas, en cada una el hilo t < stride absorbe la lista de t + stride. El hilo 0
// escribe topk_idx/topk_dist[(row_offset + r) * k ...].
__kernel __attribute__((reqd_work_group_size(TOPK_THREADS, 1, 1))) void topk_rows(__global const float *dist, __global int *topk_idx, __global float *topk_dist, int row_offset,
                                                                                  int m_chunk, int n_tiles, int k)
{
  __local float s_dist[TOPK_THREADS * MAX_K];
  __local int s_idx[TOPK_THREADS * MAX_K];
  int t = get_local_id(0);
  int r = get_group_id(0);
  float best_dist[MAX_K];
  int best_idx[MAX_K];
  scan_row(dist + (size_t)r * n_tiles, n_tiles, t, k, best_dist, best_idx);
  merge_tree(s_dist, s_idx, best_dist, best_idx, t, k);
  if (t == 0 && r < m_chunk)
  {
    for (int i = 0; i < k; ++i)
    {
      topk_idx[(size_t)(row_offset + r) * k + i] = s_idx[i];
      topk_dist[(size_t)(row_offset + r) * k + i] = s_dist[i];
    }
  }
}

// --- Etapa 4: composición ---------------------------------------------------------

// Mezcla round(alpha·tesela + (1 − alpha)·objetivo) en float, como el backend CPU.
uchar blend(uchar tile_value, uchar target_value, float alpha)
{
  float mixed = alpha * (float)tile_value + (1.0f - alpha) * (float)target_value;
  return (uchar)(mixed + ROUND_HALF);
}

// compose: work-group COMPOSE_TILE×COMPOSE_TILE, un hilo por píxel (x, y) de la imagen final,
// x = get_global_id(0), y = get_global_id(1).
// Resuelve en el dispositivo la tesela de su celda, cell = (y / tile_px) * cols + x / tile_px,
// tile = topk_idx[cell * k + choice[cell]], toma el objetivo por vecino más cercano (escala
// tile_px / CELL_PX) y escribe los 3 canales de round(alpha·tesela + (1 − alpha)·objetivo).
// No usa memoria local.
__kernel __attribute__((reqd_work_group_size(COMPOSE_TILE, COMPOSE_TILE, 1))) void compose(__global const uchar *tiles_px, __global const uchar *target_src,
                                                                                           __global const int *topk_idx, __global const int *choice, __global uchar *out, int rows,
                                                                                           int cols, int tile_px, int k, float alpha)
{
  int x = get_global_id(0);
  int y = get_global_id(1);
  int width = cols * tile_px;
  if (x >= width || y >= rows * tile_px)
  {
    return;
  }
  int cell = (y / tile_px) * cols + x / tile_px;
  int tile = topk_idx[(size_t)cell * k + choice[cell]];
  int scale = tile_px / CELL_PX;
  __global const uchar *tile_pixel = tiles_px + (((size_t)tile * tile_px + y % tile_px) * tile_px + x % tile_px) * RGB_CHANNELS;
  __global const uchar *target_pixel = target_src + ((size_t)(y / scale) * cols * CELL_PX + x / scale) * RGB_CHANNELS;
  __global uchar *out_pixel = out + ((size_t)y * width + x) * RGB_CHANNELS;
  for (int channel = 0; channel < RGB_CHANNELS; ++channel)
  {
    out_pixel[channel] = blend(tile_pixel[channel], target_pixel[channel], alpha);
  }
}
