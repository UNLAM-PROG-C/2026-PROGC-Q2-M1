# Tasks

## 1. Dependencias y base común de GPU

- [ ] 1.1 Agregar `requirements-cuda.txt` (`-r requirements.txt` + `pycuda`) y `requirements-opencl.txt` (`-r requirements.txt` + `pyopencl`), y las fracciones de memoria a `constants.py` y `env.example`; verificar que la instalación base sigue sin requerirlas (`pip install -r requirements.txt` + `pytest` en verde sin GPU).
- [ ] 1.2 Implementar `app/backends/kernel_build.py` que genera los `-D` desde `constants.py`/`color.py` con sufijo `f` en los floats; verificar con un test que cada define coincide con su constante de Python.
- [ ] 1.3 Escribir `tests/test_backend_equivalence.py` con los casos de design D8, instanciando cada backend directamente y marcando `skip` (con motivo) los que no se pueden importar o inicializar; verificar que con solo CPU corre y se saltea CUDA/OpenCL con motivo legible.

## 2. Kernels

- [ ] 2.1 Escribir `kernels/mosaic.cu` y `kernels/mosaic.cl` con `resize_tiles`, `tile_descriptors`, `cell_descriptors` y `sq_norms` (firmas y grillas de design D2/D3, comentario de mapeo por kernel, Allman según `.clang-format`); verificar que `clang-format --dry-run` no reporta cambios y que ambos archivos compilan en los backends que estén disponibles.
- [ ] 2.2 Agregar `distances_tiled` (tiles 16×16, padding 17, `row_offset`) y `topk_rows` (128 hilos, top-k en registros, merge en árbol con (dist, idx)) en ambos archivos; verificar con revisión de paridad (mismas firmas y constantes) y con los tests de equivalencia de la tarea 1.3.
- [ ] 2.3 Agregar `compose` (selección con `topk_idx` + `choice`, vecino más cercano, mezcla α en float) en ambos archivos; verificar con los tests de equivalencia en α ∈ {1, 0,5, 0}.

## 3. Backend CUDA

- [ ] 3.1 Implementar `CudaEventTimer` (pares de `pycuda.driver.Event` por etapa y por transferencia, lectura diferida tras sincronizar); verificar con un test que la suma de etapas no supera el total de reloj de pared (skip sin CUDA).
- [ ] 3.2 Implementar `CudaBackend`: contexto explícito y `close()`, compilación con las opciones de design D1, staging `pagelocked_empty` reutilizable con caída a paginable, único stream, cálculo de `m_chunk` con `mem_get_info`, flujo "encolar todo y esperar eventos en orden" de design D4, copia de `topk_idx` fuera de la medición; verificar con los tests de equivalencia y un test de que la única D→H medida es la imagen.
- [ ] 3.3 Implementar `warmup()` (compilación + trabajo sintético mínimo, tiempo de inicialización) y el manejo de `MemoryError`/errores de driver como "memoria insuficiente" sin dejar el contexto inválido; verificar con un test que fuerza un `m_chunk` imposible y luego ejecuta un trabajo chico con éxito.

## 4. Backend OpenCL

- [ ] 4.1 Implementar la selección de dispositivo (solo GPU, prioridad AMD) en una función pura testeable; verificar con tests de plataformas falsas: AMD+NVIDIA → AMD, solo NVIDIA → NVIDIA, solo CPU → no disponible.
- [ ] 4.2 Implementar `OpenClProfilingTimer` (inicio del primer comando a fin del último por etapa, a partir de `event.profile`); verificar con un test que los tiempos son positivos y no superan el total (skip sin OpenCL).
- [ ] 4.3 Implementar `OpenClBackend`: contexto y cola con `PROFILING_ENABLE`, `Program.build` con defines, staging `ALLOC_HOST_PTR` mapeados, `m_chunk` con memoria libre AMD o fracción de `GLOBAL_MEM_SIZE` acotada por `MAX_MEM_ALLOC_SIZE`, mismo flujo de design D4, `warmup()` y lectura de `topk_idx` fuera de la medición; verificar con los tests de equivalencia (en macOS corren sobre la GPU de Apple).

## 5. Detección, selección y equivalencia

- [ ] 5.1 Implementar `app/backends/registry.py` (`BackendStatus`, fábricas con import diferido, `detect_and_warmup()`, `resolve()`, `preferred_gpu()`); verificar con tests de fábricas falsas: sin bibliotecas, CUDA sin dispositivos, falla de compilación OpenCL aislada con log completo, CPU pedida con GPU disponible, backend pedido no disponible rechazado, GPU preferida CUDA con CUDA y OpenCL disponibles, OpenCL cuando falta CUDA y ninguna (con motivo) sin GPU.
- [ ] 5.2 Pasar `tests/test_backend_equivalence.py` a parametrizar con los backends que detecta el registro; verificar que pasa en la máquina de desarrollo (CPU + OpenCL) y en una máquina NVIDIA (CPU + CUDA + OpenCL), y registrar en el PR en qué hardware se corrió.
- [ ] 5.3 Agregar un script de diagnóstico `python -m app.backends.registry` que imprime el estado de todos los backends; verificar que en macOS muestra "CUDA: no disponible (biblioteca no instalada)" y la GPU de Apple para OpenCL.

## 6. Documentación

- [ ] 6.1 Agregar al README la instalación para NVIDIA (CUDA Toolkit + `requirements-cuda.txt`), AMD (drivers OpenCL/ROCm + `requirements-opencl.txt`) y macOS, la tabla de kernels/grillas de design D2, cómo correr los tests de equivalencia y el diagnóstico de backends; verificar siguiendo los pasos en al menos una plataforma con GPU.

## Workflow follow-up

- Requiere archivado previo de `agregar-nucleo-fotomosaico-cpu`.
- PR contra `develop` con tres aprobaciones; archivar antes de aplicar `agregar-worker-e-interfaz-web`.
