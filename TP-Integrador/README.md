# Fotomosaico CPU / CUDA / OpenCL

**Generador de fotomosaicos que resuelve el mismo problema en CPU secuencial y en GPU, y compara los tiempos.**

Trabajo Práctico Integrador — Programación Concurrente — UNLaM — 2.º cuatrimestre 2026

## Integrantes

| Nombre y Apellido         | DNI        |
| ------------------------- | ---------- |
| Huergo, Estefanía Belén   | 44.787.976 |
| Justiniano, Máximo        | 44.834.085 |
| Mallia, Leandro Raúl      | 43.520.743 |
| Naspleda, Julián Ezequiel | 44.391.303 |
| Ramato, Rodrigo Exequiel  | 45.129.672 |

Repositorio: [github.com/UNLAM-PROG-C/2026-PROGC-Q2-M1](https://github.com/UNLAM-PROG-C/2026-PROGC-Q2-M1) (carpeta `TP-Integrador/`).

### Compatibilidad de hardware

La aplicación detecta al arrancar qué hardware hay disponible y usa el mejor, con esta prioridad:

| Prioridad | Hardware                         | Tecnología                     | Biblioteca |
| --------- | -------------------------------- | ------------------------------ | ---------- |
| 1         | GPU NVIDIA                       | CUDA                           | PyCUDA     |
| 2         | GPU AMD, Intel, Apple (o NVIDIA) | OpenCL                         | PyOpenCL   |
| 3         | Cualquier CPU                    | Ejecución secuencial compilada | Numba      |

---

## 1. Descripción y finalidad

### ¿Qué es un fotomosaico?

Un **fotomosaico** es una imagen grande armada con cientos o miles de fotos chiquitas, como las baldosas de un mosaico. Vista de lejos se reconoce la imagen original (por ejemplo, la cara de un perro); vista de cerca, cada "baldosa" es una foto distinta (otros perros, gatos, paisajes).

Para armarlo hacen falta dos cosas:

- **La imagen objetivo:** la foto grande que se quiere reconstruir.
- **El lote de teselas:** muchas fotos chicas que se van a usar como baldosas. Cuantas más y más variadas, mejor queda el resultado.

El programa divide la imagen objetivo en una **grilla de celdas** (por ejemplo, 100 columnas × 75 filas) y, para cada celda, busca entre todas las teselas la que más se le parece en color y forma. Después pega esa tesela en el lugar de la celda. El resultado es una imagen nueva, del mismo dibujo que la original, pero hecha enteramente de otras fotos.

![Resultado de un fotomosaico en la aplicación](docs/images/ejemplo.png)

### ¿Por qué es un problema de programación concurrente / paralela?

Elegir la tesela de cada celda implica **comparar cada celda con cada tesela**. Un mosaico de 400 × 300 celdas con un lote de 8.000 teselas son **960 millones de comparaciones**, y todas son independientes entre sí: comparar la celda 1 con la tesela 5 no depende de ninguna otra comparación. Es el tipo de problema ideal para una **GPU**, que tiene miles de núcleos capaces de hacer esas comparaciones al mismo tiempo.

### Finalidad del TP

El objetivo es **didáctico**: implementar exactamente el mismo algoritmo de tres maneras y medir la diferencia.

- **CPU secuencial:** un solo hilo, sin instrucciones vectoriales (SIMD). Es la referencia contra la que se compara.
- **GPU con CUDA:** kernels propios escritos en CUDA C, para placas NVIDIA.
- **GPU con OpenCL:** los mismos kernels escritos en OpenCL C, para placas de cualquier fabricante.

Características principales:

- **Aplicación web local** con un asistente de cinco pasos: subir imágenes, elegir parámetros, ejecutar, ver el resultado (con zoom y descarga) y ver las estadísticas.
- **Detección automática de backends:** si no hay GPU, la aplicación funciona igual en CPU y explica por qué la opción GPU no está disponible.
- **Modo comparación "Ambas":** ejecuta el mismo trabajo en GPU y en CPU con los mismos datos, muestra los dos mosaicos lado a lado y la tabla de tiempos con el **speedup** de cada etapa.

---

## 2. Lenguajes y versiones

| Componente                              | Lenguaje   | Versión                                 |
| --------------------------------------- | ---------- | --------------------------------------- |
| Backend (servidor, worker, backend CPU) | Python     | 3.11 o superior (desarrollado con 3.13) |
| Kernels GPU NVIDIA                      | CUDA C     | CUDA Toolkit con `nvcc`                 |
| Kernels GPU multiplataforma             | OpenCL C   | OpenCL 1.2 o superior                   |
| Frontend (interfaz web)                 | TypeScript | 5.8                                     |
| Herramientas del frontend               | Node.js    | 20.19 o superior                        |

---

## 3. Frameworks y librerías principales

### Backend (Python)

| Área                       | Tecnología                                                             |
| -------------------------- | ---------------------------------------------------------------------- |
| API HTTP y WebSocket       | FastAPI + Uvicorn                                                      |
| Backend CPU secuencial     | Numba (compilación JIT a código nativo)                                |
| Backend CUDA               | PyCUDA                                                                 |
| Backend OpenCL             | PyOpenCL                                                               |
| Procesamiento de arrays    | NumPy                                                                  |
| Decodificación de imágenes | Pillow                                                                 |
| Concurrencia               | `multiprocessing` (procesos, colas y memoria compartida) y `threading` |
| Tests y lint               | pytest, Ruff                                                           |

### Frontend (interfaz web)

| Área                           | Tecnología                 |
| ------------------------------ | -------------------------- |
| Interfaz                       | React 18.3                 |
| Build y servidor de desarrollo | Vite 6                     |
| Gráficos comparativos          | Chart.js + react-chartjs-2 |
| Tests                          | Vitest + Testing Library   |
| Lint                           | ESLint 9, Stylelint        |

---

## 4. Arquitectura

La aplicación corre íntegramente en la máquina del usuario y se compone de **tres procesos principales**, más un pool de procesos para decodificar imágenes:

```
Navegador (React)
   │  HTTP (subidas, órdenes)  +  WebSocket (progreso en vivo)
   ▼
Proceso web (FastAPI)                 ── no hace cómputo pesado
   │  command_q ▶   (órdenes: RunJob, Shutdown)
   │  ◀ event_q     (eventos: progreso, tiempos, resultado)
   ▼
Proceso worker                        ── único dueño de la GPU
   ├─ hilo de órdenes: recibe trabajos y rechaza uno nuevo si hay otro en curso
   ├─ hilo de trabajo: ejecuta el mosaico en CPU, CUDA u OpenCL
   └─ pool de decodificación (N procesos) ──▶ memoria compartida
```

- El **proceso web** recibe las imágenes, valida los parámetros y retransmite el progreso a todas las pestañas abiertas.
- El **proceso worker** es el único que toca la GPU, así los contextos de CUDA y OpenCL quedan aislados en un solo lugar. Si el worker muere, el proceso web lo detecta y lo relanza.
- Por las colas viajan solo **mensajes chicos** (identificadores, rutas, parámetros, tiempos), nunca imágenes: los resultados se guardan en disco y el proceso web los sirve desde ahí.

El algoritmo tiene cinco etapas: carga común de imágenes (que no se compara entre backends), preparación de teselas, descriptores de color de la imagen objetivo, **matching** (distancia entre cada celda y cada tesela, quedándose con las _k_ más parecidas) y composición de la imagen final. Los colores se comparan en el espacio **CIELAB**, que se aproxima a cómo percibe el ojo humano las diferencias de color.

### Mapeo de capas a módulos

| Capa                                                            | Módulos                                                  |
| --------------------------------------------------------------- | -------------------------------------------------------- |
| Interfaz web                                                    | `frontend/src/`                                          |
| Proceso web (API, WebSocket, subidas)                           | `backend/app/web/`                                       |
| Proceso worker (órdenes, ejecución de trabajos)                 | `backend/app/worker/`                                    |
| Carga de imágenes (pool de procesos, cache)                     | `backend/app/loading/`                                   |
| Núcleo (parámetros, contrato de backend, tiempos, verificación) | `backend/app/core/`                                      |
| Backends CPU, CUDA y OpenCL; detección                          | `backend/app/backends/`                                  |
| Kernels GPU                                                     | `backend/kernels/mosaic.cu`, `backend/kernels/mosaic.cl` |
| Benchmark                                                       | `backend/benchmark.py`, `backend/app/bench/`             |

### Patrones de diseño

**Strategy.** El algoritmo del mosaico es siempre el mismo; lo que cambia es dónde se ejecuta y cómo se mide.

- `MosaicBackend` (`app/core/backend.py`) es el contrato común que cumplen `CpuBackend`, el backend CUDA y el backend OpenCL. El worker y el modo comparación los usan de manera intercambiable, sin saber cuál es cuál.
- `StageTimer` (`app/core/timing.py`) define cómo se toma el tiempo de una etapa, con tres estrategias: `PerfCounterTimer` (reloj de la CPU), `CudaEventTimer` (eventos de CUDA) y `OpenClProfilingTimer` (contadores de profiling de OpenCL). Cada backend mide con el mecanismo más preciso de su plataforma.

**Template Method.** `BaseBackend.run()` (`app/core/backend.py`) fija la secuencia de etapas, el momento en que se toma cada tiempo y cuándo se informa el progreso; cada backend implementa solo los pasos. Así se garantiza que los tres miden exactamente las mismas etapas y que la comparación es justa. `GpuBackend` (`app/backends/gpu_base.py`) agrega un segundo nivel: el orden de los siete kernels y sus grillas está escrito una sola vez, y CUDA y OpenCL solo implementan las primitivas de su API (reservar memoria, copiar, lanzar y sincronizar).

**Productor/Consumidor.** Se usa en dos lugares:

- **Pool de decodificación** (`app/loading/tile_loader.py`): el proceso padre produce tareas (ruta de la imagen e índice) y los procesos del pool las consumen, decodificando cada imagen y escribiéndola directamente en memoria compartida. Decodificar miles de JPEG es un trabajo pesado que así se reparte entre todos los núcleos.
- **Colas entre el proceso web y el worker** (`command_q` y `event_q`): el proceso web produce órdenes que consume el worker, y el worker produce eventos de progreso que consume un hilo lector del proceso web. Así la interfaz sigue respondiendo mientras la GPU o la CPU calculan.

---

## 5. Restricciones de hardware

- **No es obligatorio tener GPU.** Sin GPU la aplicación funciona solo en CPU, y las opciones "GPU" y "Ambas" aparecen deshabilitadas con el motivo.
- **CUDA** requiere una placa NVIDIA, el driver actualizado y el [CUDA Toolkit](https://developer.nvidia.com/cuda-downloads) con `nvcc` en el PATH (los kernels se compilan la primera vez). En Windows, además, Visual Studio o las _Build Tools_ con las herramientas de C++ (`cl.exe`), que el backend busca solo.
- **OpenCL** requiere un driver con soporte OpenCL: en NVIDIA viene con el driver; en AMD, Adrenalin (Windows) o ROCm (Linux); en macOS viene con el sistema (OpenCL 1.2, deprecado por Apple pero funcional). Si hay más de una GPU, la variable `OPENCL_DEVICE` permite elegir cuál usar.
- **Memoria de la GPU:** el matching se hace por bloques de celdas según la memoria disponible (`GPU_MEMORY_FRACTION` y `OPENCL_MEMORY_FRACTION`), por eso funciona también en placas con poca memoria. Si no entra ni un bloque mínimo, el trabajo falla con "memoria insuficiente" y la aplicación sigue usable.
- **Memoria RAM:** cada tesela cargada ocupa unos 48 KB; un lote de 8.000 teselas usa alrededor de 400 MB.
- **Límites configurables:** subidas de hasta 2 GB (`MOSAIC_MAX_UPLOAD_MB`), hasta 20.000 archivos por lote y una imagen final de hasta 150 millones de píxeles.
- **El backend CPU es estrictamente secuencial** (un hilo, sin SIMD).

---

## 6. Sistema operativo y navegador

### Sistema operativo

- **Windows 10/11:** soporta CPU, CUDA y OpenCL. Es la plataforma donde se desarrolló y midió.
- **Linux:** soporta CPU, CUDA y OpenCL.
- **macOS:** soporta CPU y OpenCL. CUDA no existe en macOS.

### Navegador

Cualquier navegador moderno con soporte de WebSocket (Chrome, Edge, Firefox, Safari). La interfaz se abre en `http://127.0.0.1:5173`. Solo se necesita internet la primera vez, para descargar las dependencias; después la aplicación funciona sin conexión.

---

## 7. Puesta en marcha

### Requisitos previos

- Python 3.11 o superior.
- Node.js 20.19 o superior (opcional: si no está, el script lo instala dentro del entorno virtual).
- Para usar GPU, los drivers indicados en "Restricciones de hardware".

### Ejecución

Desde la carpeta `TP-Integrador/`:

```powershell
.\start.ps1              # Windows (PowerShell)
```

```bash
./start.sh               # Linux / macOS
```

El script crea el entorno virtual `.venv`, instala las dependencias de Python (y la biblioteca de GPU que corresponda al hardware), instala las del frontend, levanta el backend y el frontend, e imprime la URL para abrir en el navegador. **Ctrl+C** detiene todo. La opción `--cpu-only` (`-CpuOnly` en PowerShell) evita instalar las bibliotecas de GPU.

El proyecto incluye un lote de prueba en `muestras/lote_teselas_perros_gatos/` (180 fotos de perros y gatos) y tres imágenes objetivo de ejemplo en `muestras/`.

---
