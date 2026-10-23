# Design

## Context

- Parte del diseño general del cambio `agregar-nucleo-fotomosaico-cpu` (estructura, patrones, precisión numérica D3). Acá se detalla solo lo de GPU.
- El contrato (`BaseBackend.run()` como Template Method y `StageTimer` como Strategy) ya existe: CUDA y OpenCL implementan los pasos y su propio timer.
- La máquina de desarrollo es macOS: CUDA no se puede probar localmente, y OpenCL sí (GPU Apple, OpenCL 1.2). Los tests de CUDA corren en una máquina NVIDIA de algún integrante o se saltean.

## Goals / Non-Goals

**Goals:**
- Kernels gemelos en CUDA C y OpenCL C, legibles y comentados, con el mismo mapeo de hilos y los mismos tamaños de bloque.
- Medición separada de cómputo por etapa y de transferencias, comparable entre APIs.
- Resultados equivalentes a los del backend CPU, dentro de la tolerancia definida en el cambio 1.

**Non-Goals:**
- Máximo rendimiento posible (por ejemplo cuBLAS/CLBlast, *tensor cores*, `half`): se privilegia que el kernel se pueda explicar y que sea idéntico en ambas APIs.
- Varias GPUs a la vez, o streams concurrentes.

## Decisions

### D1. Constantes compartidas

`app/backends/kernel_build.py` genera una vez la lista de `-D` a partir de `app/core/constants.py` y `color.py` (por ejemplo `-DTILE_SRC_PX=128 -DDESC_GRID=8 -DDESC_DIM=192 -DMATMUL_TILE=16 -DTOPK_THREADS=128 -DMAX_K=16 ...`), con sufijo `f` en los floats. Se pasa a `SourceModule` (con `no_extern_c=True`) y a `Program.build`, con las opciones de compilación por defecto de cada API. Los kernels no tienen literales con significado de negocio.

### D2. Tamaños de bloque y grillas

Constantes: `BLOCK_1D = 256`, `MATMUL_TILE = 16`, `TOPK_THREADS = 128`, `MAX_K = 16`, `COMPOSE_TILE = 16`. En OpenCL el *global size* se redondea hacia arriba al múltiplo del *local size* y cada kernel descarta los hilos sobrantes con un `if`, igual que en CUDA.

| Kernel | Hilo procesa | Bloque / work-group | Grilla / global size |
| --- | --- | --- | --- |
| `resize_tiles` | 1 píxel (3 canales) de `tiles_px` | 256 | `⌈N·tile_px² / 256⌉` |
| `tile_descriptors` | 1 celda 8×8 de una tesela (bloque 16×16 de la fuente) | 256 | `⌈N·64 / 256⌉` |
| `cell_descriptors` | 1 píxel del bloque 8×8 de una celda | 256 | `⌈M·64 / 256⌉` |
| `sq_norms` | 1 vector de 192 | 256 | `⌈n / 256⌉` (se lanza para teselas y para celdas) |
| `distances_tiled` | 1 elemento `[fila, tesela]` del bloque | 16×16 | `(⌈N/16⌉, ⌈m_chunk/16⌉)` |
| `topk_rows` | porción intercalada de una fila | 128 | `m_chunk` bloques |
| `compose` | 1 píxel (3 canales) de la imagen final | 16×16 | `(⌈W/16⌉, ⌈H/16⌉)`, `W = cols·tile_px`, `H = rows·tile_px` |

### D3. Firmas de los kernels

Se escriben en CUDA; en OpenCL son iguales con `__kernel`, `__global`, y con `uchar` en lugar de `unsigned char`. Los punteros se calculan siempre con `row_offset` explícito en lugar de aritmética sobre el puntero del host, porque OpenCL no permite desplazar un `cl_mem` sin crear sub-buffers alineados.

```c
// Un hilo por píxel de salida: gid -> (tile, y, x). Promedio entero del bloque f×f, f = 128 / tile_px.
__global__ void resize_tiles(const unsigned char *tiles_src, unsigned char *tiles_px,
                             int n_tiles, int tile_px);

// Un hilo por (tile, cy, cx) de la miniatura 8×8: promedia el bloque 16×16 en sRGB por canal
// y lo convierte a Lab. Escribe 3 floats en tile_desc[tile*192 + (cy*8+cx)*3].
__global__ void tile_descriptors(const unsigned char *tiles_src, float *tile_desc, int n_tiles);

// Un hilo por (cell, py, px): convierte un píxel de target_src a Lab.
__global__ void cell_descriptors(const unsigned char *target_src, float *cell_desc, int rows, int cols);

// Un hilo por vector: suma de cuadrados en orden k = 0..191.
__global__ void sq_norms(const float *desc, float *norms, int n_vectors);

// Bloque 16×16. Hilo (ty, tx) calcula dist[r, c] con r = by*16+ty (fila del chunk), c = bx*16+tx.
// 12 pasos de tiling (192 / 16): carga a_tile[16][16] de cell_desc y b_tile[16][17] de tile_desc
// (+1 de padding contra conflictos de bancos), acumula el producto escalar y escribe
// (cell_norms[row_offset + r] + tile_norms[c]) - 2.0f * acc.
__global__ void distances_tiled(const float *cell_desc, const float *tile_desc,
                                const float *cell_norms, const float *tile_norms, float *dist,
                                int row_offset, int m_chunk, int n_tiles);

// Un bloque de 128 hilos por fila del chunk. Hilo t recorre c = t, t+128, ... (accesos coalescidos)
// con su top-k en registros (arrays de MAX_K con bucles desenrollados), los vuelca a memoria
// compartida (128·16·8 B = 16 KiB) y se combinan en árbol (7 rondas, merge de listas ordenadas
// con la comparación (dist, idx)). El hilo 0 escribe topk_idx/topk_dist[(row_offset + r)*k ...].
__global__ void topk_rows(const float *dist, int *topk_idx, float *topk_dist,
                          int row_offset, int m_chunk, int n_tiles, int k);

// Bloque 16×16, un hilo por píxel (x, y) de salida: cell = (y / tile_px)*cols + x / tile_px,
// tile = topk_idx[cell*k + choice[cell]], objetivo por vecino más cercano con escala tile_px/8,
// mezcla alpha*tile + (1-alpha)*target redondeada al entero más cercano.
__global__ void compose(const unsigned char *tiles_px, const unsigned char *target_src,
                        const int *topk_idx, const int *choice, unsigned char *out,
                        int rows, int cols, int tile_px, int k, float alpha);
```

Notas:
- Si un hilo de `topk_rows` ve menos de `k` columnas (N < 128·k), completa su lista con `(+∞, INT_MAX)`, que siempre pierde la comparación; como `k ≤ N`, el resultado final nunca contiene relleno.

### D4. Flujo de un trabajo en GPU y progreso sin burbujas

1. Reservar todos los buffers del dispositivo (incluida la imagen de salida y `topk` de `[M, k]`), calcular `m_chunk` con la memoria restante.
2. Copiar al staging pinned (host) y encolar H→D de `tiles_src`, `target_src` y `choice`.
3. Encolar **todas** las etapas y todos los bloques del matching, registrando eventos de inicio y fin.
4. Encolar D→H de la imagen.
5. Recién entonces el host espera los eventos **en orden** y llama a `on_progress` a medida que se cumplen. Como todo ya está encolado, esperar no deja la GPU ociosa entre bloques (alternativa descartada: sincronizar después de cada bloque, que agrega una burbuja de lanzamiento por bloque).
6. Sincronizar, tomar el reloj de pared, calcular los tiempos de eventos y, fuera de la medición, copiar `topk_idx` para validación.

Con N = 5.000 y M = 40.000 son pocas decenas de bloques, muy por debajo del límite de lanzamientos pendientes del driver.

### D5. Transferencias y memoria pinned

- CUDA: `pagelocked_empty` para staging de entrada y salida. Se informan **dos números**: copia a staging (reloj de pared en el host) y DMA (eventos). Así queda a la vista el costo de pinnear, que es parte del aprendizaje.
- OpenCL: buffers `ALLOC_HOST_PTR` mapeados (`enqueue_map_buffer` con `WRITE_INVALIDATE_REGION`), copia en el host, `unmap`, y `enqueue_copy` buffer→buffer medido por profiling.
- Los staging se reservan por trabajo y se reutilizan si el siguiente trabajo entra en ellos: reservar cientos de MB pinned cuesta milisegundos.
- La imagen final puede ser grande (M = 40.000 con `tile_px = 64` da ~490 MB): si la reserva pinned falla, se cae a memoria paginable y se informa (spec `backend-cuda`).

### D6. Tamaño de bloque del matching

- CUDA: `pycuda.driver.mem_get_info()` después de reservar todo lo demás; `m_chunk = ((free·GPU_MEMORY_FRACTION) // (N·4))` redondeado hacia abajo a múltiplo de 16 y acotado por M.
- OpenCL: si existe `cl_amd_device_attribute_query`, se usa la memoria libre; si no, `GLOBAL_MEM_SIZE·OPENCL_MEMORY_FRACTION` menos lo reservado. En ambos casos se acota por `MAX_MEM_ALLOC_SIZE`.
- Las fracciones van a `constants.py` y se pueden sobrescribir desde `env.example`.

### D7. Detección y registro (Factory)

`app/backends/registry.py` define `BackendStatus(name, available, device_name, reason, init_ms, warnings)` y una fábrica por backend que importa PyCUDA/PyOpenCL **dentro** de un `try` (así importar el proyecto nunca falla sin GPU). `detect_and_warmup()` crea y precalienta cada backend; cualquier excepción se convierte en `available=False` con un motivo corto (`biblioteca no instalada`, `sin dispositivos CUDA`, `sin GPU OpenCL`, `error de compilación de kernels`, `error de driver`) y el detalle va al log. `resolve(names)` devuelve los backends pedidos por nombre y rechaza los no disponibles. `preferred_gpu()` devuelve la GPU que usa la opción "GPU" de la interfaz: CUDA si está disponible, si no OpenCL, si no `None` con un motivo combinado ("no se detectó una GPU compatible"). Con una placa NVIDIA en la que fallan PyCUDA o el CUDA Toolkit, OpenCL sobre la misma placa queda como GPU preferida.

- CUDA usa el dispositivo 0. El contexto se crea con `Device(0).make_context()` en el proceso que llama a `detect_and_warmup()` y se libera con `pop()` + `detach()` en `close()`; el cambio 3 garantiza que ese proceso es el worker y que todas las llamadas ocurren en su hilo principal.
- OpenCL: GPUs de todas las plataformas, primero las de vendor que contenga "AMD" o "Advanced Micro Devices".
- `warmup()` compila y ejecuta un trabajo sintético mínimo para pagar la carga del módulo y el primer lanzamiento; su duración es el tiempo de inicialización.

### D8. Tests

`tests/test_backend_equivalence.py` parametriza sobre los backends que detecta el registro (los no disponibles se marcan `skip` con el motivo) y compara contra CPU con la tolerancia del cambio 1 (descriptores y `topk_dist` con `EQUIVALENCE_LAB_TOLERANCE`, `topk_idx` coincidente en al menos `MIN_MATCHING_CELLS_RATIO` de las celdas, e imagen con diferencia máxima de 1 nivel por canal en las celdas cuyo `topk_idx` coincide), en estos casos: N y M no múltiplos de 16; N < 128 (hilos de `topk_rows` con menos columnas que `k`); teselas duplicadas (empates); `tile_px` ∈ {16, 32, 64}; `k` ∈ {1, 5, 16}; `alpha` ∈ {1, 0,5, 0}; y bloque de matching forzado a 16 celdas. Más tests unitarios del registro con fábricas falsas (falla de compilación aislada, selección respetada, GPU preferida).

## Risks / Trade-offs

- [Nadie del grupo tiene una GPU AMD] → OpenCL se prueba sobre NVIDIA o sobre la GPU de Apple; la prioridad AMD se cubre con tests del registro con plataformas falsas.
- [OpenCL de Apple está deprecado y puede comportarse distinto] → Es plataforma de desarrollo, no de demostración; si falla, el registro lo marca no disponible con el motivo.
- [Casi-empates resueltos distinto por CPU y GPU] → Esperable sin forzar igualdad exacta (cambio 1, design D3); los tests usan tolerancia y la comparación del cambio 4 informa cuántas celdas difieren.
- [Copiar `topk_idx` para validación fuera de la medición contradice "al host solo vuelve la imagen"] → Se resuelve así la contradicción entre ese requisito y que `MosaicResult` incluya `topk_idx`: la copia existe, pero no está dentro de la medición. Son `M·k·4` bytes (2,5 MB en el peor caso).
- [`topk_rows` con un bloque por fila desperdicia hilos cuando N es chico] → Es el diseño pedido y es didáctico; el benchmark muestra justamente que para problemas chicos la GPU puede no ganar.

## Open Questions

- Si conviene exponer una variable de entorno para elegir el dispositivo CUDA u OpenCL en máquinas con varias GPUs: se puede agregar después sin cambiar las specs.
