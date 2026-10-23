// Kernels CUDA del fotomosaico (cambio 2, design D2/D3).
//
// Gemelo de kernels/mosaic.cl: mismos kernels, mismos argumentos en el mismo
// orden y el mismo mapeo hilo -> dato. Solo cambian los calificadores de cada
// API (__global__ / __kernel, __shared__ / __local, __syncthreads / barrier).
//
// Ninguna constante del algoritmo está escrita acá: TILE_SRC_PX, DESC_DIM,
// MATMUL_TILE, TOPK_THREADS, MAX_K, las constantes de color, etc. llegan como
// -DNOMBRE=valor desde app/backends/kernel_build.py (misma fuente que el CPU).
//
// Cada kernel declara con __launch_bounds__ el tamaño de bloque con el que se
// lanza (la misma constante que usa el host y que el reqd_work_group_size de
// OpenCL), así el compilador reserva registros para ese tamaño.
//
// Los índices de los buffers grandes se calculan en size_t para no desbordar
// int con matrices de distancias de varios GB.

#include <climits>

// Hilos por bloque de los kernels 2D (para __launch_bounds__).
#define MATMUL_THREADS (MATMUL_TILE * MATMUL_TILE)
#define COMPOSE_THREADS (COMPOSE_TILE * COMPOSE_TILE)

extern "C"
{
  // --- Funciones auxiliares (inline en cada hilo) ------------------------------

  // Inversa de la curva gamma de sRGB para un canal en [0, 255].
  __device__ float linearize(float channel)
  {
    float value = channel / CHANNEL_MAX;
    if (value <= SRGB_LINEAR_THRESHOLD)
    {
      return value / SRGB_LINEAR_SLOPE;
    }
    return powf((value + SRGB_GAMMA_OFFSET) / SRGB_GAMMA_SCALE, SRGB_GAMMA_EXPONENT);
  }

  // Función f(t) de CIELAB.
  __device__ float lab_f(float t)
  {
    if (t > LAB_EPSILON)
    {
      return cbrtf(t);
    }
    return t / LAB_LINEAR_DIVISOR + LAB_LINEAR_OFFSET;
  }

  // Convierte un color sRGB (canales en [0, 255]) a Lab y lo escribe en out[0..2].
  __device__ void write_lab(float red, float green, float blue, float *out)
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
  __device__ bool precedes(float dist_a, int idx_a, float dist_b, int idx_b)
  {
    return dist_a < dist_b || (dist_a == dist_b && idx_a < idx_b);
  }

  // --- Etapa 1: preparación de teselas ------------------------------------------

  // Inicio de la tesela `tile` en tiles_src [N, TILE_SRC_PX, TILE_SRC_PX, RGB_CHANNELS].
  __device__ const unsigned char *tile_source(const unsigned char *tiles_src, int tile)
  {
    return tiles_src + (size_t)tile * TILE_SRC_PX * TILE_SRC_PX * RGB_CHANNELS;
  }

  // Promedio entero redondeado de un canal en el bloque factor×factor que empieza en (y0, x0).
  __device__ unsigned char block_mean_rounded(const unsigned char *src, int y0, int x0, int channel, int factor)
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
    return (unsigned char)((total + area / 2) / area);
  }

  // Promedio float de un canal en el bloque DESC_BLOCK_PX×DESC_BLOCK_PX que empieza en (y0, x0).
  __device__ float block_mean_srgb(const unsigned char *src, int y0, int x0, int channel)
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
  // Índice: gid = blockIdx.x * BLOCK_1D + threadIdx.x -> (tile, y, x) con
  // tile = gid / tile_px², y = (gid / tile_px) % tile_px, x = gid % tile_px.
  // Cada hilo promedia con redondeo entero el bloque f×f de la tesela fuente,
  // f = TILE_SRC_PX / tile_px. No usa memoria compartida.
  __global__ void __launch_bounds__(BLOCK_1D) resize_tiles(const unsigned char *tiles_src, unsigned char *tiles_px, int n_tiles, int tile_px)
  {
    int gid = blockIdx.x * BLOCK_1D + threadIdx.x;
    if (gid >= n_tiles * tile_px * tile_px)
    {
      return;
    }
    int tile = gid / (tile_px * tile_px);
    int y = (gid / tile_px) % tile_px;
    int x = gid % tile_px;
    int factor = TILE_SRC_PX / tile_px;
    const unsigned char *src = tile_source(tiles_src, tile);
    for (int channel = 0; channel < RGB_CHANNELS; ++channel)
    {
      tiles_px[(size_t)gid * RGB_CHANNELS + channel] = block_mean_rounded(src, y * factor, x * factor, channel, factor);
    }
  }

  // tile_descriptors: un hilo por (tile, cy, cx) de la miniatura DESC_GRID×DESC_GRID.
  // Índice: gid -> tile = gid / DESC_GRID², pos = gid % DESC_GRID² = cy * DESC_GRID + cx.
  // Promedia en sRGB el bloque DESC_BLOCK_PX×DESC_BLOCK_PX de la fuente, lo pasa a Lab y
  // escribe 3 floats en tile_desc[tile * DESC_DIM + pos * 3]. No usa memoria compartida.
  __global__ void __launch_bounds__(BLOCK_1D) tile_descriptors(const unsigned char *tiles_src, float *tile_desc, int n_tiles)
  {
    int gid = blockIdx.x * BLOCK_1D + threadIdx.x;
    if (gid >= n_tiles * DESC_GRID * DESC_GRID)
    {
      return;
    }
    int tile = gid / (DESC_GRID * DESC_GRID);
    int pos = gid % (DESC_GRID * DESC_GRID);
    int y0 = (pos / DESC_GRID) * DESC_BLOCK_PX;
    int x0 = (pos % DESC_GRID) * DESC_BLOCK_PX;
    const unsigned char *src = tile_source(tiles_src, tile);
    float red = block_mean_srgb(src, y0, x0, 0);
    float green = block_mean_srgb(src, y0, x0, 1);
    float blue = block_mean_srgb(src, y0, x0, 2);
    write_lab(red, green, blue, tile_desc + (size_t)gid * RGB_CHANNELS);
  }

  // --- Etapa 2: descriptores del objetivo ---------------------------------------

  // cell_descriptors: un hilo por (cell, py, px), un píxel del bloque CELL_PX×CELL_PX de una celda.
  // Índice: gid -> cell = gid / CELL_PX², pos = gid % CELL_PX² = py * CELL_PX + px; la celda
  // está en la fila cell / cols y la columna cell % cols. Escribe 3 floats en
  // cell_desc[cell * DESC_DIM + pos * 3]. No usa memoria compartida.
  __global__ void __launch_bounds__(BLOCK_1D) cell_descriptors(const unsigned char *target_src, float *cell_desc, int rows, int cols)
  {
    int gid = blockIdx.x * BLOCK_1D + threadIdx.x;
    if (gid >= rows * cols * CELL_PX * CELL_PX)
    {
      return;
    }
    int cell = gid / (CELL_PX * CELL_PX);
    int pos = gid % (CELL_PX * CELL_PX);
    int y = (cell / cols) * CELL_PX + pos / CELL_PX;
    int x = (cell % cols) * CELL_PX + pos % CELL_PX;
    const unsigned char *pixel = target_src + ((size_t)y * cols * CELL_PX + x) * RGB_CHANNELS;
    write_lab(pixel[0], pixel[1], pixel[2], cell_desc + (size_t)gid * RGB_CHANNELS);
  }

  // sq_norms: un hilo por vector de DESC_DIM floats (se lanza para teselas y para celdas).
  // Índice: gid = número de vector. Suma de cuadrados en orden k = 0..DESC_DIM-1.
  __global__ void __launch_bounds__(BLOCK_1D) sq_norms(const float *desc, float *norms, int n_vectors)
  {
    int gid = blockIdx.x * BLOCK_1D + threadIdx.x;
    if (gid >= n_vectors)
    {
      return;
    }
    const float *row = desc + (size_t)gid * DESC_DIM;
    float total = 0.0f;
    for (int d = 0; d < DESC_DIM; ++d)
    {
      total += row[d] * row[d];
    }
    norms[gid] = total;
  }

  // --- Etapa 3: matching -----------------------------------------------------------

  // Producto escalar de una fila de a_tile con una de b_tile (un paso del tiling).
  __device__ float tile_dot(const float *a_row, const float *b_row)
  {
    float acc = 0.0f;
    for (int i = 0; i < MATMUL_TILE; ++i)
    {
      acc += a_row[i] * b_row[i];
    }
    return acc;
  }

  // distances_tiled: bloque MATMUL_TILE×MATMUL_TILE, un hilo por elemento dist[r, c] del bloque
  // de celdas, con r = blockIdx.y * MATMUL_TILE + threadIdx.y (fila del chunk, celda
  // row_offset + r) y c = blockIdx.x * MATMUL_TILE + threadIdx.x (tesela).
  // Memoria compartida, en DESC_DIM / MATMUL_TILE pasos:
  //   a_tile[ty][tx] = cell_desc[row_offset + fila ty del bloque][paso * MATMUL_TILE + tx]
  //   b_tile[ty][tx] = tile_desc[tesela ty del bloque][paso * MATMUL_TILE + tx]
  // b_tile tiene una columna de padding (MATMUL_TILE + 1): al leer b_tile[tx][d], los hilos de
  // un warp caen en bancos distintos. Los hilos fuera de rango cargan 0 y no escriben, pero
  // participan de las barreras. Resultado: (‖c‖² + ‖t‖²) − 2·c·t.
  __global__ void __launch_bounds__(MATMUL_THREADS)
      distances_tiled(const float *cell_desc, const float *tile_desc, const float *cell_norms, const float *tile_norms, float *dist, int row_offset, int m_chunk, int n_tiles)
  {
    __shared__ float a_tile[MATMUL_TILE][MATMUL_TILE];
    __shared__ float b_tile[MATMUL_TILE][MATMUL_TILE + 1];
    int tx = threadIdx.x;
    int ty = threadIdx.y;
    int r = blockIdx.y * MATMUL_TILE + ty;
    int c = blockIdx.x * MATMUL_TILE + tx;
    int load_tile = blockIdx.x * MATMUL_TILE + ty;
    float acc = 0.0f;
    for (int step = 0; step < DESC_DIM / MATMUL_TILE; ++step)
    {
      int d = step * MATMUL_TILE + tx;
      a_tile[ty][tx] = r < m_chunk ? cell_desc[(size_t)(row_offset + r) * DESC_DIM + d] : 0.0f;
      b_tile[ty][tx] = load_tile < n_tiles ? tile_desc[(size_t)load_tile * DESC_DIM + d] : 0.0f;
      __syncthreads();
      acc += tile_dot(a_tile[ty], b_tile[tx]);
      __syncthreads();
    }
    if (r < m_chunk && c < n_tiles)
    {
      dist[(size_t)r * n_tiles + c] = (cell_norms[row_offset + r] + tile_norms[c]) - 2.0f * acc;
    }
  }

  // Inserta (dist, idx) en la lista ordenada de k elementos en registros. El bucle se desenrolla
  // con índices constantes (así la lista vive en registros): en cada posición se queda el menor
  // de los dos y el mayor sigue hacia el final; el último se descarta.
  __device__ void insert_sorted(float *best_dist, int *best_idx, float dist, int idx, int k)
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
  // compartida y deja en la de `self` las k menores. Como se toman k de 2k, ninguna lista
  // se agota antes de terminar.
  __device__ void merge_lists(float *s_dist, int *s_idx, int self, int other, int k)
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
  __device__ void scan_row(const float *row, int n_tiles, int t, int k, float *best_dist, int *best_idx)
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

  // Vuelca la lista del hilo t a memoria compartida y combina las listas en árbol: en cada ronda
  // el hilo t < stride absorbe la lista de t + stride. Al final, la lista 0 es el top-k de la fila.
  __device__ void merge_tree(float *s_dist, int *s_idx, const float *best_dist, const int *best_idx, int t, int k)
  {
#pragma unroll
    for (int i = 0; i < MAX_K; ++i)
    {
      s_dist[t * MAX_K + i] = best_dist[i];
      s_idx[t * MAX_K + i] = best_idx[i];
    }
    __syncthreads();
    for (int stride = TOPK_THREADS / 2; stride > 0; stride /= 2)
    {
      if (t < stride)
      {
        merge_lists(s_dist, s_idx, t, t + stride, k);
      }
      __syncthreads();
    }
  }

  // topk_rows: un bloque de TOPK_THREADS hilos por fila r = blockIdx.x del chunk.
  // El hilo t recorre c = t, t + TOPK_THREADS, ... (accesos coalescidos) con su top-k en
  // registros; si ve menos de k columnas, su lista queda con relleno (+inf, INT_MAX), que
  // siempre pierde. Luego vuelca su lista a memoria compartida
  // (TOPK_THREADS·MAX_K·(4 + 4) B = 16 KiB) y se combinan en árbol: log2(TOPK_THREADS)
  // rondas, en cada una el hilo t < stride absorbe la lista de t + stride. El hilo 0
  // escribe topk_idx/topk_dist[(row_offset + r) * k ...].
  __global__ void __launch_bounds__(TOPK_THREADS) topk_rows(const float *dist, int *topk_idx, float *topk_dist, int row_offset, int m_chunk, int n_tiles, int k)
  {
    __shared__ float s_dist[TOPK_THREADS * MAX_K];
    __shared__ int s_idx[TOPK_THREADS * MAX_K];
    int t = threadIdx.x;
    int r = blockIdx.x;
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
  __device__ unsigned char blend(unsigned char tile_value, unsigned char target_value, float alpha)
  {
    float mixed = alpha * (float)tile_value + (1.0f - alpha) * (float)target_value;
    return (unsigned char)(mixed + ROUND_HALF);
  }

  // compose: bloque COMPOSE_TILE×COMPOSE_TILE, un hilo por píxel (x, y) de la imagen final,
  // x = blockIdx.x * COMPOSE_TILE + threadIdx.x, y = blockIdx.y * COMPOSE_TILE + threadIdx.y.
  // Resuelve en el dispositivo la tesela de su celda, cell = (y / tile_px) * cols + x / tile_px,
  // tile = topk_idx[cell * k + choice[cell]], toma el objetivo por vecino más cercano (escala
  // tile_px / CELL_PX) y escribe los 3 canales de round(alpha·tesela + (1 − alpha)·objetivo).
  // No usa memoria compartida.
  __global__ void __launch_bounds__(COMPOSE_THREADS) compose(const unsigned char *tiles_px, const unsigned char *target_src, const int *topk_idx, const int *choice,
                                                             unsigned char *out, int rows, int cols, int tile_px, int k, float alpha)
  {
    int x = blockIdx.x * COMPOSE_TILE + threadIdx.x;
    int y = blockIdx.y * COMPOSE_TILE + threadIdx.y;
    int width = cols * tile_px;
    if (x >= width || y >= rows * tile_px)
    {
      return;
    }
    int cell = (y / tile_px) * cols + x / tile_px;
    int tile = topk_idx[(size_t)cell * k + choice[cell]];
    int scale = tile_px / CELL_PX;
    const unsigned char *tile_pixel = tiles_px + (((size_t)tile * tile_px + y % tile_px) * tile_px + x % tile_px) * RGB_CHANNELS;
    const unsigned char *target_pixel = target_src + ((size_t)(y / scale) * cols * CELL_PX + x / scale) * RGB_CHANNELS;
    unsigned char *out_pixel = out + ((size_t)y * width + x) * RGB_CHANNELS;
    for (int channel = 0; channel < RGB_CHANNELS; ++channel)
    {
      out_pixel[channel] = blend(tile_pixel[channel], target_pixel[channel], alpha);
    }
  }
}
