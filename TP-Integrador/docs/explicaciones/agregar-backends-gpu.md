# Backends GPU (CUDA y OpenCL)

**En una frase:** las 4 etapas del fotomosaico se pasan a 7 kernels propios (gemelos en CUDA y OpenCL) que se encolan todos en un único stream/cola en orden. El host solo espera al final, mientras reenvía el progreso a medida que la GPU va pasando por los marcadores.

## Flujo

1. **Host, hilo principal:** el registro crea cada backend con una fábrica y lo precalienta. Eso compila `mosaic.cu`/`mosaic.cl` con las constantes como `-D` y corre un trabajo mínimo. Si algo falla, ese backend queda "no disponible" y se sigue con los demás ([registry.py:146](TP-Integrador/backend/app/backends/registry.py#L146), [kernel_build.py:94](TP-Integrador/backend/app/backends/kernel_build.py#L94)).
2. **Host:** reserva todos los buffers del dispositivo y, con la memoria que queda, calcula `m_chunk`, o sea cuántas celdas por bloque del matching entran en la matriz de distancias ([gpu_base.py:230](TP-Integrador/backend/app/backends/gpu_base.py#L230), [gpu_base.py:100](TP-Integrador/backend/app/backends/gpu_base.py#L100)).
3. **Host → GPU:** copia las entradas a un staging pinned y **encola** las copias H→D asíncronas ([cuda/backend.py:158-167](TP-Integrador/backend/app/backends/cuda/backend.py#L158)).
4. **GPU:** el host encola, sin esperar nada, `resize_tiles`, `tile_descriptors`, `sq_norms` ×2 y `cell_descriptors`. Después, por cada bloque de celdas, `distances_tiled` + `topk_rows`, y al final `compose` ([gpu_base.py:244-301](TP-Integrador/backend/app/backends/gpu_base.py#L244)).
5. **Host:** encola la copia D→H de la imagen, espera los marcadores de progreso en orden, sincroniza y copia el staging a un array propio ([gpu_base.py:303-314](TP-Integrador/backend/app/backends/gpu_base.py#L303)).

```
 Host (1 hilo)  ──encola──▶ [ H2D | k1..k5 | dist₀ topk₀ | dist₁ topk₁ | ... | compose | D2H ]  stream/cola en orden
      ▲                          marcador ▲          marcador ▲                         marcador ▲
      └──── drain(): espera cada marcador y llama a on_progress ───────────────────────────────┘
```

## Concurrencia y paralelismo

| Unidad de ejecución | Cantidad (hilos por bloque × bloques) | Qué hace | Dónde |
|---|---|---|---|
| Hilo del host | 1 | Encola copias y kernels; después espera eventos | [gpu_base.py:263](TP-Integrador/backend/app/backends/gpu_base.py#L263) |
| `resize_tiles`, `tile_descriptors`, `cell_descriptors`, `sq_norms` | 256 × ⌈n/256⌉ (1D) | 1 hilo por píxel, por posición del descriptor o por vector | [mosaic.cu:111](TP-Integrador/backend/kernels/mosaic.cu#L111), [gpu_base.py:330](TP-Integrador/backend/app/backends/gpu_base.py#L330) |
| `distances_tiled` | 16×16 × (⌈N/16⌉, ⌈m_chunk/16⌉) | 1 hilo por elemento `dist[celda, tesela]` | [mosaic.cu:212](TP-Integrador/backend/kernels/mosaic.cu#L212), [gpu_base.py:271](TP-Integrador/backend/app/backends/gpu_base.py#L271) |
| `topk_rows` | 128 × `m_chunk` | 1 bloque por fila; cada hilo recorre una porción intercalada | [mosaic.cu:334](TP-Integrador/backend/kernels/mosaic.cu#L334), [gpu_base.py:283](TP-Integrador/backend/app/backends/gpu_base.py#L283) |
| `compose` | 16×16 × (⌈W/16⌉, ⌈H/16⌉) | 1 hilo por píxel de la imagen final | [mosaic.cu:369](TP-Integrador/backend/kernels/mosaic.cu#L369), [gpu_base.py:289](TP-Integrador/backend/app/backends/gpu_base.py#L289) |

Es **paralelismo de datos**: miles de hilos de GPU corren el mismo kernel sobre datos distintos. Los hilos sobrantes del último bloque salen con un `if` (en OpenCL, el global size es bloques × work-group: [opencl/backend.py:216-219](TP-Integrador/backend/app/backends/opencl/backend.py#L216)). Entre kernels **no** hay paralelismo: el stream es uno solo y se ejecutan uno detrás del otro. Lo que sí hay es **concurrencia host/GPU**: el host termina de encolar mientras la GPU ya está trabajando. El GIL no influye, porque el host casi no calcula.

## Sincronización y comunicación

- **Memoria compartida + `__syncthreads()` en `distances_tiled`**: en 192/16 = 12 pasos, cada hilo carga un valor de `a_tile` (celdas) y uno de `b_tile` (teselas). La 1ª barrera garantiza que el tile está completo antes del producto. La 2ª, que nadie lo pise mientras otro hilo todavía lo lee ([mosaic.cu:223-231](TP-Integrador/backend/kernels/mosaic.cu#L223)). `b_tile` tiene una columna de padding (`MATMUL_TILE + 1`) para que un warp no choque en el mismo banco ([mosaic.cu:216](TP-Integrador/backend/kernels/mosaic.cu#L216)). En OpenCL es igual, con `__local` y `barrier(CLK_LOCAL_MEM_FENCE)` ([mosaic.cl:222](TP-Integrador/backend/kernels/mosaic.cl#L222)).
- **Top-k en registros + merge en árbol (`topk_rows`)**: cada hilo `t` recorre `c = t, t+128, …` (accesos coalescidos) y arma su top-k ordenado en registros ([mosaic.cu:292](TP-Integrador/backend/kernels/mosaic.cu#L292)). Después vuelca su lista a memoria compartida (128·16·8 B = 16 KiB) y se combinan en log₂(128) = 7 rondas: el hilo `t < stride` absorbe la lista de `t + stride`, con una barrera por ronda ([mosaic.cu:308-325](TP-Integrador/backend/kernels/mosaic.cu#L308)). Es una **reducción paralela**. Al final, el hilo 0 escribe el resultado.
- **Stream único / cola en orden**: CUDA crea un solo `Stream` ([cuda/backend.py:121](TP-Integrador/backend/app/backends/cuda/backend.py#L121)) y OpenCL una `CommandQueue` en orden ([opencl/backend.py:95](TP-Integrador/backend/app/backends/opencl/backend.py#L95)). El orden de la cola **es** la sincronización entre kernels: `compose` lee `topk_idx` recién cuando terminaron todos los `topk_rows`.
- **Eventos/marcadores para el progreso (Observer diferido)**: `report()` solo registra un marcador en la cola; `drain()` los espera en orden y recién ahí avisa ([gpu_base.py:146-156](TP-Integrador/backend/app/backends/gpu_base.py#L146), [cuda/backend.py:196-204](TP-Integrador/backend/app/backends/cuda/backend.py#L196)). Si se sincronizara después de cada bloque, quedaría una burbuja ociosa en la GPU entre bloque y bloque.
- **Medición**: en CUDA, un par de eventos por etapa que se leen al final con `time_till` ([cuda/timing.py:33-50](TP-Integrador/backend/app/backends/cuda/timing.py#L33)). En OpenCL, `PROFILING_ENABLE` y el span entre el primer y el último evento de la etapa ([opencl/timing.py:18](TP-Integrador/backend/app/backends/opencl/timing.py#L18)). Registrar un evento no bloquea al host.
- **Transferencias pinned**: el staging `pagelocked_empty` permite DMA asíncrono real ([cuda/backend.py:152](TP-Integrador/backend/app/backends/cuda/backend.py#L152)). Si no se puede reservar, se cae a memoria paginable y queda anotado en el resultado. En OpenCL se usan buffers `ALLOC_HOST_PTR` mapeados (el map es bloqueante), el host escribe ahí, se hace el unmap y después `enqueue_copy` ([opencl/backend.py:174-188](TP-Integrador/backend/app/backends/opencl/backend.py#L174)).

## Riesgos y cómo se evitan

- **Barreras divergentes (deadlock en la GPU)**: en `distances_tiled`, los hilos fuera de rango no hacen `return`: cargan 0 y pasan igual por las barreras ([mosaic.cu:226-232](TP-Integrador/backend/kernels/mosaic.cu#L226)). En `merge_tree`, la barrera está fuera del `if (t < stride)`.
- **Reuso del buffer `dist` entre bloques (WAR)**: `distances_tiled` del bloque i+1 pisa la matriz que lee `topk_rows` del bloque i. No hace falta sincronizar porque la cola es en orden.
- **Staging reutilizado entre trabajos**: el próximo trabajo recién lo sobrescribe después de que `_download` y `_release` sincronizaron ([gpu_base.py:321-328](TP-Integrador/backend/app/backends/gpu_base.py#L321)).
- **Un solo hilo por backend**: el stream, el timer, `_m_chunk` y los staging son estado compartido sin lock. El `push/pop` del contexto CUDA ([cuda/backend.py:85](TP-Integrador/backend/app/backends/cuda/backend.py#L85)) lo hace usable desde cualquier hilo, pero **no** permite dos `run()` concurrentes sobre el mismo backend. El diseño (D7) delega esa garantía al worker del cambio 3.

## Para recordar

- **Paralelismo de datos + tiling en memoria compartida**: un hilo por elemento y una barrera entre "cargar" y "usar".
- **Reducción en árbol**: k-mejores en O(log P) rondas con barreras, en vez de que un solo hilo recorra toda la fila.
- **Asincronía host/dispositivo**: encolar todo, medir con eventos y sincronizar una sola vez al final.
