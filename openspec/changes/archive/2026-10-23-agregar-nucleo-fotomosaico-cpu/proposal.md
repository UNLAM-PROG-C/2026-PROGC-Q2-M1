# Proposal

## Why

El TP integrador es un generador de fotomosaicos cuyo objetivo es **didáctico**: mostrar la diferencia de tiempos entre resolver el mismo problema en paralelo en GPU (CUDA, OpenCL) y secuencialmente en CPU. Antes de poder comparar nada hace falta (a) definir con precisión el algoritmo que las tres implementaciones deben reproducir, (b) la etapa común de carga de imágenes y (c) la implementación de referencia: el backend CPU secuencial, que además es el único que siempre está disponible.

Este es el **cambio 1 de 5** de la propuesta inicial del proyecto:

1. `agregar-nucleo-fotomosaico-cpu` (este): carga común, contrato del algoritmo y de los backends, backend CPU secuencial.
2. `agregar-backends-gpu`: kernels y backends CUDA y OpenCL, detección de backends.
3. `agregar-worker-e-interfaz-web`: proceso worker, backend FastAPI, frontend React desacoplado con stepper (CPU o GPU) y script de arranque con venv.
4. `agregar-modo-comparacion`: ejecución del mismo trabajo en CPU y GPU ("Ambas"), estadísticas comparativas, speedup y verificación.
5. `agregar-benchmark`: script `benchmark.py` y cierre de la documentación.

## What Changes

- Se crea el backend Python del TP en `TP-Integrador/backend/` (estructura de paquetes, `requirements*.txt`, `env.example`, configuración de linter/tests, `Makefile`) y el README base en `TP-Integrador/`. Las dependencias se instalan en el entorno virtual `TP-Integrador/.venv`. La carpeta `TP-Integrador/frontend/` llega en el cambio 3. Reemplaza el placeholder `TP-Integrador/file`.
- Etapa común de carga: decodificación de teselas en un pool de procesos (EXIF, RGB, recorte cuadrado central, 128×128) sobre un array compartido preasignado, y preparación de la imagen objetivo (`(cols·8)×(rows·8)`). Se mide aparte y se puede reutilizar.
- Definición formal del algoritmo de fotomosaico (preparación de teselas, descriptores Lab 8×8, distancias, top-k con desempate determinista, selección con semilla, composición con mezcla α), común a los tres backends.
- Contrato común de backends (`MosaicBackend`, `MosaicParams`, `MosaicResult`, tiempos por etapa, `warmup()` excluido de la medición, callback de progreso).
- Backend **CPU secuencial** con Numba `@njit` de un solo hilo y **sin vectorización SIMD**, con bucles que reflejan uno a uno los kernels de GPU.
- Tests: conversión sRGB→Lab contra valores de referencia, carga (EXIF, recorte, derivación de filas), reglas del algoritmo (desempate, `k = 1`, mezcla) y pipeline CPU completo sobre un conjunto sintético.

## Capabilities

### New Capabilities
- `carga-de-imagenes`: decodificación y normalización de teselas e imagen objetivo, orden determinista de teselas, decodificación en paralelo y reutilización de la carga.
- `algoritmo-fotomosaico`: definición del algoritmo, común a todos los backends (parámetros, etapas, desempate, selección, composición).
- `contrato-de-backend`: interfaz común que cumple todo backend: inicialización (warmup) separada, tiempos por etapa, progreso y equivalencia de resultados.
- `backend-cpu-secuencial`: implementación secuencial de referencia, siempre disponible, de un solo hilo y sin SIMD.

### Modified Capabilities
<!-- Ninguna: no hay specs previas en el proyecto. -->

## Impact

- Código nuevo en `TP-Integrador/backend/` (`app/core`, `app/loading`, `app/backends/cpu`, `tests/`). No toca los TPs anteriores.
- Dependencias base: `numpy`, `numba`, `pillow`; de desarrollo: `pytest`, `ruff`.
- Las decisiones numéricas de este cambio condicionan los kernels CUDA/OpenCL del cambio 2: cualquier ajuste posterior al algoritmo debe hacerse en las tres implementaciones a la vez.
