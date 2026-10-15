# Design

## Context

- `TP-Integrador/` solo contiene un placeholder. No hay código previo del integrador; los TPs anteriores en Python (`TP1-parte1/02_Python`, `TP1-parte2/02_Python`) usan `src/`, `Makefile` con targets `build/run/bench/clean` y README en español: se mantiene ese estilo de entrega.
- `CLAUDE.md` fija: Google Style Guide con **2 espacios** de indentación, funciones de menos de ~15 líneas, sin números mágicos, patrones de diseño documentados, comentarios en español rioplatense y código en inglés.
- La máquina de desarrollo actual es macOS: no hay CUDA y OpenCL está disponible (deprecado) vía Apple. Todo lo de este cambio tiene que funcionar y testearse sin GPU.
- Este diseño es el **diseño general del proyecto**. Los cambios 2 a 5 lo referencian y solo detallan lo propio (kernels, procesos, comparación, benchmark).

## Goals / Non-Goals

**Goals:**
- Un algoritmo definido con precisión suficiente para que los tres backends resuelvan exactamente el mismo problema, con código simple.
- Una implementación CPU que sirva de referencia y de material didáctico (bucle ↔ grilla de hilos).
- Un contrato de backend que permita agregar CUDA y OpenCL en el cambio 2 sin tocar el resto.

**Non-Goals:**
- Optimizar el backend CPU (cache blocking, SIMD, multihilo): sería otra cosa que "secuencial".
- Solapar transferencias y cómputo en GPU (streams múltiples): complicaría la medición, que es el objetivo.
- Calidad estética avanzada del mosaico (corrección de color por celda, penalización de repeticiones por vecindad).

## Decisions

### D1. La propuesta se divide en 5 cambios encadenados

Ver la hoja de ruta en `proposal.md`. Cada cambio **solo agrega** capacidades nuevas (no modifica las de otro cambio no archivado), así que se pueden validar en paralelo y aplicar y archivar en orden. Alternativa descartada: un único cambio gigante, con decenas de tareas y un PR imposible de revisar por tres personas.

### D2. Estructura de archivos

```
TP-Integrador/
├── README.md                  # instalación por plataforma, uso, patrones (crece en cada cambio)
├── Makefile                   # build / run / test / bench / clean, como en los TPs anteriores
├── pyproject.toml             # configuración de ruff (indent-width = 2) y pytest
├── requirements.txt           # base: numpy, numba, pillow (+ fastapi, uvicorn en el cambio 3)
├── requirements-cuda.txt      # -r requirements.txt + pycuda              (cambio 2)
├── requirements-opencl.txt    # -r requirements.txt + pyopencl            (cambio 2)
├── requirements-dev.txt       # pytest, ruff (+ httpx, matplotlib más adelante)
├── env.example                # plantilla de variables de entorno, sin secretos
├── benchmark.py               #                                           (cambio 5)
├── kernels/
│   ├── mosaic.cu              #                                           (cambio 2)
│   └── mosaic.cl              #                                           (cambio 2)
├── static/                    # index.html, app.js, styles.css, vendor/   (cambios 3 y 4)
├── app/
│   ├── core/
│   │   ├── constants.py       # única fuente de verdad de constantes (128, 8, 192, 16, 256...)
│   │   ├── params.py          # MosaicParams, validación, derivación de rows
│   │   ├── result.py          # MosaicResult, StageTimings
│   │   ├── backend.py         # Protocol MosaicBackend + BaseBackend (Template Method)
│   │   ├── timing.py          # StageTimer (Strategy) + PerfCounterTimer
│   │   ├── color.py           # matriz sRGB→XYZ, blanco D65, constantes Lab, referencia float64
│   │   ├── choice.py          # generación de choice con semilla
│   │   └── verification.py    # digests por celda y comparación          (cambio 4)
│   ├── loading/
│   │   ├── decode.py          # funciones que corren dentro del pool (EXIF, recorte, resize)
│   │   ├── tile_loader.py     # pool spawn + SharedMemory + orden determinista
│   │   ├── target_loader.py   # objetivo + derivación de grilla
│   │   └── cache.py           # reutilización de la última carga
│   ├── backends/
│   │   ├── registry.py        # Factory + detección                       (cambio 2)
│   │   ├── kernel_build.py    # -D compartidos para .cu y .cl             (cambio 2)
│   │   ├── cpu/
│   │   │   ├── __init__.py    # desactiva la vectorización de Numba antes de importarlo
│   │   │   ├── stages.py      # funciones @njit, una por kernel
│   │   │   ├── backend.py     # CpuBackend
│   │   │   └── calibration.py # costos unitarios para estimar duración    (cambio 3)
│   │   ├── cuda/              # backend.py, timing.py                     (cambio 2)
│   │   └── opencl/            # backend.py, timing.py, device.py          (cambio 2)
│   ├── worker/                # messages.py, runner.py, process.py        (cambio 3)
│   ├── web/                   # server.py, routes.py, uploads.py, hub.py  (cambio 3)
│   ├── bench/                 # defaults.py, synthetic.py, report.py      (cambio 5)
│   ├── config.py              # variables de entorno                      (cambio 3)
│   └── main.py                # arranque de uvicorn                       (cambio 3)
└── tests/
    ├── conftest.py            # fábricas de lotes sintéticos con semilla
    ├── test_color.py
    ├── test_params.py
    ├── test_loading.py
    ├── test_algorithm_rules.py
    └── test_cpu_backend.py
```

Se agregan `app/core` y `app/loading` a la estructura pedida (`app/web`, `app/worker`, `app/backends/*`), porque el contrato y la carga no pertenecen a ningún backend ni al worker.

### D3. Precisión numérica: se aceptan diferencias pequeñas

Los tres backends usan `float32` y las funciones estándar de cada plataforma (`powf`/`cbrtf` en GPU, `np.power`/`np.cbrt` en Numba), con las opciones de compilación por defecto. Por eso los resultados **no son idénticos bit a bit**: las bibliotecas matemáticas de CUDA, de cada driver OpenCL y de LLVM pueden diferir en el último dígito, los compiladores de GPU fusionan `a*b + c` en una instrucción FMA y el orden de las sumas puede cambiar. Esas diferencias solo cambian el resultado en casi-empates (dos teselas a distancias casi iguales de una celda).

Se prioriza un código simple sobre la igualdad exacta. En consecuencia:
- los tests de equivalencia comparan descriptores y `topk_dist` con tolerancia (`EQUIVALENCE_LAB_TOLERANCE`) y exigen que `topk_idx` coincida en al menos `MIN_MATCHING_CELLS_RATIO` (99 %) de las celdas;
- el modo comparación (cambio 4) informa cuántas celdas difieren en lugar de suponer igualdad;
- se mantienen el desempate por índice menor y la semilla de `choice`, que hacen que cada backend sea reproducible consigo mismo.

Alternativa descartada: forzar la igualdad exacta (LUT de linealización, raíz cúbica propia, aritmética entera, compilación sin FMA). Era factible, pero agregaba código y reglas que no aportan a la comparación de tiempos.

### D4. "Secuencial" también significa sin SIMD (aclaración)

La propuesta prohíbe NumPy vectorizado porque usa SIMD. Con el mismo criterio, LLVM (debajo de Numba) **auto-vectoriza** bucles simples. Se desactiva con `NUMBA_LOOP_VECTORIZE=0` y `NUMBA_SLP_VECTORIZE=0`, fijadas con `os.environ.setdefault` en `app/backends/cpu/__init__.py` antes de importar Numba (y documentadas en `env.example`). Un test verifica `numba.config.LOOP_VECTORIZE == 0`. Además se evita la promoción silenciosa a float64: toda constante y acumulador es `np.float32`.

### D5. Estructura del backend CPU

- Una función `@njit(cache=False)` por kernel (`resize_tiles`, `tile_descriptors`, `cell_descriptors`, `sq_norms`, `distances`, `topk_rows`, `compose`), con el bucle externo sobre lo que en GPU es la grilla y un comentario "una iteración = un hilo de `<kernel>`". Funciones auxiliares `@njit(inline="always")` (`srgb_to_lab`, `insert_sorted`) para respetar el largo de ~15 líneas sin cambiar el código generado.
- El matching **no** se fusiona (distancias del bloque → top-k del bloque), igual que en GPU. Fusionarlo sería más rápido en CPU, pero rompería la correspondencia uno a uno que pide la propuesta.
- El bucle de bloques está en Python y llama a funciones compiladas por bloque, lo que permite reportar progreso sin `objmode`. Tamaño de bloque: `CPU_DISTANCE_BUDGET_BYTES // (N · 4)`.

### D6. Patrones de diseño

| Patrón | Dónde | Por qué |
| --- | --- | --- |
| Strategy | `MosaicBackend` (CPU/CUDA/OpenCL) y `StageTimer` (perf_counter / eventos CUDA / profiling OpenCL) | El algoritmo es el mismo y cambia cómo se ejecuta y cómo se mide. |
| Template Method | `BaseBackend.run()` fija la secuencia de etapas, el cronometraje y el progreso; cada backend implementa los pasos | Garantiza que las tres implementaciones midan exactamente las mismas etapas. |
| Observer | Callback `on_progress` | El backend no conoce a quién le reporta (test, worker, benchmark). |
| Productor/Consumidor | Pool de decodificación (y en el cambio 3, colas web↔worker) | Reparto de trabajo entre procesos. |

No se usa Singleton: el único recurso global (contexto de GPU) vive dentro del worker y se pasa explícitamente.

### D7. Carga común

- `multiprocessing.get_context("spawn")` en **todo** el proyecto: `fork` después de crear un contexto CUDA rompe el driver, y `spawn` es el comportamiento por defecto en macOS y Windows, así que se evita tener dos caminos.
- Las teselas se escriben en un `multiprocessing.shared_memory.SharedMemory` de `[N, 128, 128, 3]`; cada tarea recibe `(ruta, índice, nombre del bloque compartido)`. Si hay archivos inválidos, el padre compacta el array al final. El índice sale del orden lexicográfico de las rutas relativas.
- Remuestreo con Pillow `LANCZOS` para teselas y objetivo (etapa común, no afecta la igualdad entre backends). `Image.MAX_IMAGE_PIXELS` se mantiene activo contra bombas de descompresión.
- `cache.py` guarda solo la última carga (clave: huella del lote; para el objetivo, huella + `cols`): con N = 5.000, `tiles_src` ocupa ~245 MB.

### D8. Formato de código Python

Se sigue `CLAUDE.md` (2 espacios), aunque los TPs anteriores en Python usan 4: la regla explícita de la cátedra tiene prioridad. `ruff format` con `indent-width = 2` y `ruff check` con reglas de Google (docstrings, nombres). Nada de esto aplica a `.cu`/`.cl`, que siguen el `.clang-format` del repo (Allman).

### D9. Dependencias

`requirements.txt` no puede expresar dependencias opcionales, así que se separan en `requirements-cuda.txt` y `requirements-opencl.txt` (cada uno incluye el base). Alternativa descartada: líneas comentadas en un único archivo, que nadie instala por error pero tampoco a propósito.

## Risks / Trade-offs

- [Casi-empates resueltos distinto por cada backend] → Esperable con float32 y funciones estándar (design D3); los tests usan tolerancia y la comparación cuenta las celdas distintas.
- [Desactivar la vectorización hace que la CPU parezca más lenta que "una CPU normal"] → Es la definición de secuencial que pide la propuesta; el README lo explica y el benchmark puede mostrar la variante vectorizada como dato aparte en el futuro.
- [Numba promueve a float64 sin avisar si se mezcla un literal Python] → Constantes `np.float32` de módulo y un test que compara contra una versión NumPy float32 de referencia.
- [Pool de decodificación con `spawn` tiene costo de arranque] → Se crea una vez y se reutiliza; su tiempo es parte de la etapa común, que no se compara.

## Open Questions

- Rango de `cols` (mínimo y máximo) y presupuesto de memoria por defecto del matching en CPU: se fijan como constantes nombradas al implementar; no cambian las specs.
