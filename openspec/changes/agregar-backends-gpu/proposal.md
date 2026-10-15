# Proposal

## Why

Con el algoritmo definido y la referencia CPU funcionando (cambio `agregar-nucleo-fotomosaico-cpu`), falta lo que el TP quiere mostrar: el mismo problema resuelto en paralelo en GPU. Se necesitan dos implementaciones, CUDA para NVIDIA y OpenCL para AMD u otras GPUs, con **los mismos kernels, la misma lógica y los mismos tamaños de bloque**, para que la comparación GPU vs. CPU (y CUDA vs. OpenCL en la misma placa) sea justa.

Es el **cambio 2 de 5**. Depende del cambio 1 (contrato de backend y definición del algoritmo).

## What Changes

- Kernels propios en `kernels/mosaic.cu` (CUDA C) y `kernels/mosaic.cl` (OpenCL C): `resize_tiles`, `tile_descriptors`, `cell_descriptors`, `sq_norms`, `distances_tiled`, `topk_rows`, `compose`, comentados con el mapeo hilo → dato.
- Backend CUDA con PyCUDA: contexto explícito (sin `pycuda.autoinit`), memoria *pinned*, un único stream, tiempos con `pycuda.driver.Event`, transferencias medidas aparte y tamaño de bloque del matching según la memoria libre.
- Backend OpenCL con PyOpenCL: prioridad a dispositivos AMD, buffers `ALLOC_HOST_PTR`, una única command queue con `PROFILING_ENABLE`, tiempos por eventos de profiling.
- Detección de backends disponibles y selección: estado de cada backend con nombre del dispositivo o motivo de indisponibilidad, modo "Automático" (CUDA > OpenCL > CPU), y respeto estricto de la elección del usuario.
- Tests de equivalencia: los tres backends producen resultados equivalentes, con tolerancia de punto flotante, sobre conjuntos sintéticos (se saltean los backends no disponibles).

## Capabilities

### New Capabilities
- `kernels-gpu`: conjunto de kernels compartido por CUDA y OpenCL: descomposición en hilos, tamaños de bloque, constantes compartidas y documentación.
- `backend-cuda`: ejecución del algoritmo con CUDA: contexto, memoria, stream, medición y gestión de memoria del dispositivo.
- `backend-opencl`: ejecución del algoritmo con OpenCL: selección de dispositivo, memoria, command queue y medición por profiling.
- `deteccion-de-backends`: detección al inicio, estado informable de cada backend, aislamiento de fallas de inicialización y política de selección.

### Modified Capabilities
<!-- Ninguna: las capacidades del cambio 1 no cambian. -->

## Impact

- Código nuevo en `TP-Integrador/kernels/`, `app/backends/cuda/`, `app/backends/opencl/`, `app/backends/registry.py` y tests.
- Dependencias opcionales: `pycuda` (requiere CUDA Toolkit) en `requirements-cuda.txt` y `pyopencl` en `requirements-opencl.txt`. Sin ellas la aplicación sigue funcionando solo con CPU.
- README: instalación para NVIDIA (CUDA Toolkit) y AMD (drivers OpenCL/ROCm), y cómo correr los tests de equivalencia.
