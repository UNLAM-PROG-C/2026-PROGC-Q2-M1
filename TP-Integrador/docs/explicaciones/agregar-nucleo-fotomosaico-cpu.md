# Núcleo del fotomosaico y backend CPU secuencial

**En una frase:** carga el lote de teselas en paralelo con un pool de procesos que escriben en memoria compartida, y después arma el fotomosaico con un backend CPU de un solo hilo (Numba, sin SIMD) que sirve de referencia para los backends GPU.

## Flujo

1. **Proceso padre:** `LoadCache.load` calcula la huella del lote (ruta, tamaño, mtime). Si coincide con la última carga, reutiliza las teselas sin decodificar nada ([cache.py:81](TP-Integrador/backend/app/loading/cache.py#L81)).
2. **Padre (productor):** lista los archivos en orden lexicográfico, crea un `SharedMemory` de `[N, 128, 128, 3]` y arma una tarea `(ruta, índice, nombre del bloque, N)` por archivo ([tile_loader.py:101-103](TP-Integrador/backend/app/loading/tile_loader.py#L101)).
3. **Procesos del pool (consumidores, uno por núcleo):** cada uno decodifica su imagen (EXIF, recorte, Lanczos) y la escribe en `tiles[index]` del bloque compartido ([decode.py:78](TP-Integrador/backend/app/loading/decode.py#L78)). Por la cola solo vuelve `(índice, error)`.
4. **Padre:** consume todos los resultados, copia el bloque a un array propio, libera la memoria compartida y compacta sacando los inválidos ([tile_loader.py:105-109](TP-Integrador/backend/app/loading/tile_loader.py#L105)). La imagen objetivo se carga en el padre, sin pool ([target_loader.py:41](TP-Integrador/backend/app/loading/target_loader.py#L41)).
5. **Padre, un hilo:** `BaseBackend.run` ejecuta en orden las 4 etapas (preparar teselas, descriptores del objetivo, matching, composición), cada una cronometrada y con progreso ([core/backend.py:118-129](TP-Integrador/backend/app/core/backend.py#L118)).

```
            tareas (ruta, índice, nombre shm)
 [Padre] ───────────────────────────────▶ [Worker 1..P]
    ▲  ◀──── (índice, error) ──────────────     │
    │                                           ▼ escribe tiles[i]
    └──────── lee/copia ──── [SharedMemory N×128×128×3]
```

## Concurrencia y paralelismo

| Unidad de ejecución | Cantidad | Qué hace | Dónde |
|---|---|---|---|
| Proceso padre | 1 | Productor: reparte tareas, junta errores, copia y compacta | [tile_loader.py:98](TP-Integrador/backend/app/loading/tile_loader.py#L98) |
| Procesos del pool (`spawn`) | `os.cpu_count()` por defecto | Decodifican teselas y las escriben en la memoria compartida | [tile_loader.py:57](TP-Integrador/backend/app/loading/tile_loader.py#L57), [tile_loader.py:95](TP-Integrador/backend/app/loading/tile_loader.py#L95) |
| Funciones `@njit` del backend CPU | 1 hilo | Cada bucle recorre lo que en GPU sería la grilla de hilos de un kernel | [stages.py:95](TP-Integrador/backend/app/backends/cpu/stages.py#L95) |

La decodificación es **paralela de verdad**: son procesos separados, así que el GIL no los frena (cada uno tiene su intérprete). El backend CPU es **secuencial a propósito**: sin `parallel=True` y con la autovectorización de LLVM apagada ([cpu/\_\_init\_\_.py:15-20](TP-Integrador/backend/app/backends/cpu/__init__.py#L15)), para que sea la línea base honesta contra la que se compara la GPU. Cada comentario "una iteración = un hilo del kernel X" marca el futuro paralelismo de datos.

## Sincronización y comunicación

- **Cola interna del `Pool`** entre padre y workers: viajan solo tareas chicas y `(índice, error)`, de a `DECODE_CHUNKSIZE = 8` tareas por envío para amortizar el costo de la comunicación ([tile_loader.py:104](TP-Integrador/backend/app/loading/tile_loader.py#L104)).
- **`SharedMemory`** entre workers y padre: los píxeles (unos 245 MB para N = 5.000) no se serializan; cada worker se conecta por nombre y cierra su handle al terminar ([decode.py:76-80](TP-Integrador/backend/app/loading/decode.py#L76)).
- **Barrera implícita:** el dict por comprensión agota el iterador de `imap_unordered`, así que el padre no lee el bloque hasta que todas las tareas terminaron ([tile_loader.py:105-106](TP-Integrador/backend/app/loading/tile_loader.py#L105)).
- **`close()` + `join()`** del pool al salir del `with` del `TileLoader` ([tile_loader.py:79-80](TP-Integrador/backend/app/loading/tile_loader.py#L79)).
- **Callback de progreso (Observer)** dentro del mismo hilo: el matching informa el avance entre bloques de celdas ([cpu/backend.py:96](TP-Integrador/backend/app/backends/cpu/backend.py#L96)).

## Riesgos y cómo se evitan

- **Carrera al escribir en la memoria compartida:** no hay lock porque cada tarea escribe una porción disjunta (`tiles[index]`), con el índice fijado por el padre antes de repartir. Por eso el resultado es el mismo sin importar cuántos procesos haya ni en qué orden terminen (`imap_unordered`).
- **Liberar la memoria antes de tiempo:** el `close()`/`unlink()` está en un `finally` que solo se alcanza después de consumir todos los resultados. Si se cortara la iteración por una excepción en el padre, el bloque se libera con workers todavía corriendo; en ese caso fallarían al conectarse, pero no corrompen nada.
- **`fork` con CUDA:** se usa siempre `spawn` para no heredar un contexto CUDA roto en los hijos (design D7). Detalles a tener en cuenta: en Python < 3.13 el *fallback* sin `track=False` ([decode.py:58-59](TP-Integrador/backend/app/loading/decode.py#L58)) puede generar avisos de "leaked shared_memory" del resource tracker; y `LoadCache` no tiene lock, así que asume que lo usa un solo hilo.

## Para recordar

- **Productor/Consumidor con pool de procesos:** el padre produce tareas y los workers las consumen; para datos grandes se comunica por memoria compartida y por la cola solo van metadatos.
- **Determinismo por particionado:** si cada trabajador escribe en su propia porción, preasignada, no hace falta sincronizar las escrituras.
- **Línea base secuencial:** el backend CPU tiene la misma forma que los kernels (un bucle por cada grilla) para medir speedup contra algo comparable.
