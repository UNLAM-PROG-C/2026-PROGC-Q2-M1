# TP Integrador: generador de fotomosaicos

Un fotomosaico arma una imagen objetivo con una grilla de imágenes chicas (teselas): para cada celda se elige la tesela que más se le parece. El objetivo del TP es **didáctico**: resolver exactamente el mismo problema en paralelo en GPU (CUDA y OpenCL) y secuencialmente en CPU, y mostrar la diferencia de tiempos.

Estado actual (cambio 3 de 5, `agregar-worker-e-interfaz-web`): carga común de imágenes, definición del algoritmo, contrato común de backends, **backend CPU secuencial**, **backends GPU CUDA y OpenCL** con kernels propios, detección de backends y una **aplicación local**: un proceso worker dueño de los contextos de GPU, un proceso web (FastAPI) y una interfaz React con un stepper de tres pasos. El modo comparación (CPU y GPU a la vez) y el benchmark llegan en los cambios siguientes (ver `openspec/changes/`).

## Levantar la aplicación

### Con el script (recomendado)

Desde `TP-Integrador/`:

```bash
./start.sh                # macOS / Linux
```

```powershell
.\start.ps1              # Windows (PowerShell)
```

Opciones (las dos sintaxis valen en ambos scripts):

| Opción | Qué hace |
| --- | --- |
| `--cpu-only` (`-CpuOnly`) | No instala ninguna biblioteca de GPU: la aplicación queda solo con CPU. |
| `--reinstall` (`-Reinstall`) | Ignora las huellas guardadas: reinstala las dependencias de Python, reintenta la biblioteca de GPU y vuelve a correr `npm ci`. |
| `--help` | Muestra la ayuda. |

Qué hace y dónde instala (cada paso se saltea si ya está hecho):

1. Verifica Python ≥ 3.11 y crea `TP-Integrador/.venv` si no existe. **Todo** se instala dentro de ese venv; nada va al Python del sistema.
2. Instala `backend/requirements.txt` si cambió desde la última vez (la huella queda en `.venv/.mosaic-stamp`).
3. Biblioteca de GPU: si `nvidia-smi` responde, `requirements-cuda.txt` (PyCUDA); si no hay NVIDIA o PyCUDA no compila (falta el CUDA Toolkit), `requirements-opencl.txt` (PyOpenCL). Una falla es solo una advertencia: la aplicación arranca con CPU. No se reintenta en cada arranque; para reintentar (por ejemplo, después de instalar el CUDA Toolkit) se usa `--reinstall`.
4. Node.js: usa el `node` del `PATH` si es ≥ 20.19; si no, instala `nodeenv` y Node LTS **dentro del venv**. Corre `npm ci` en `frontend/` si falta `node_modules` o cambió `package-lock.json`.
5. Crea `backend/.env` y `frontend/.env` a partir de sus `env.example` si no existen.
6. Levanta el backend, espera a que `/api/state` responda, levanta el frontend e imprime la URL (por defecto `http://127.0.0.1:5173`). **Ctrl+C** detiene los dos sin dejar procesos huérfanos.

La primera vez necesita internet (pip y npm); después la aplicación funciona sin conexión: no usa CDN y la tipografía viene instalada con npm.

### Backend y frontend por separado

Backend (desde `TP-Integrador/backend/`, con el venv ya creado como en "Instalación"):

```powershell
..\.venv\Scripts\python.exe -m app.main     # Windows
```

```bash
../.venv/bin/python -m app.main            # Linux / macOS (o: make run)
```

Escucha en `http://127.0.0.1:8000`. No necesita ningún archivo del frontend: la API se puede probar con `curl` (por ejemplo `curl http://127.0.0.1:8000/api/state`). Ctrl+C lo apaga de forma ordenada: el proceso web le pide al worker que termine, el worker cierra el pool de decodificación y libera los contextos de GPU, y si no termina en `MOSAIC_SHUTDOWN_TIMEOUT_S` se lo termina a la fuerza. Al arrancar, el worker detecta y precalienta los backends (compila los kernels y Numba): la interfaz habilita la ejecución recién cuando termina (unos segundos).

Frontend (desde `TP-Integrador/frontend/`, con Node ≥ 20.19):

```bash
npm ci          # una vez
npm run dev     # servidor de Vite en http://127.0.0.1:5173
npm run lint    # ESLint (Google TS style, Allman) + stylelint (sin colores literales fuera de tokens.css)
npm test        # Vitest
npm run build   # chequeo de tipos + build de producción (no hace falta para usar la aplicación)
```

### Variables de entorno

Ninguna es obligatoria. Cada carpeta tiene su `env.example`; se copia a `.env` (que no se versiona) y se edita. Las del backend también se pueden exportar en la terminal, y tienen prioridad sobre el `.env`.

`backend/env.example`:

| Variable | Por defecto | Para qué |
| --- | --- | --- |
| `MOSAIC_HOST` | `127.0.0.1` | Interfaz del proceso web. Otro valor expone la aplicación a la red. |
| `MOSAIC_PORT` | `8000` | Puerto del proceso web. |
| `MOSAIC_FRONTEND_ORIGIN` | `http://127.0.0.1:5173` | Único origen aceptado por CORS y por el WebSocket. |
| `MOSAIC_TEMP_DIR` | `<temp del sistema>/fotomosaico` | Subidas y resultados; sus carpetas `tiles/`, `targets/` y `jobs/` se vacían al arrancar y al apagar. |
| `MOSAIC_MAX_UPLOAD_MB` | `2048` | Tamaño máximo de una subida y de lo descomprimido de un zip (413 si se supera). |
| `MOSAIC_MAX_ZIP_ENTRIES` | `20000` | Archivos máximos de un lote. |
| `MOSAIC_MAX_OUTPUT_PIXELS` | `150000000` | Píxeles máximos de la imagen final. |
| `MOSAIC_PREVIEW_MAX_SIDE` | `2048` | Lado mayor de la vista previa del resultado. |
| `MOSAIC_TILE_SAMPLE_COUNT` | `12` | Miniaturas del lote que muestra el paso 1. |
| `MOSAIC_CPU_CONFIRM_SECONDS` | `60` | Si la estimación de CPU lo supera, se pide confirmación. |
| `MOSAIC_DECODE_PROCESSES` | `0` | Procesos del pool de decodificación (0 = uno por núcleo). |
| `MOSAIC_SHUTDOWN_TIMEOUT_S` | `15` | Espera al worker al apagar antes de terminarlo a la fuerza. |
| `NUMBA_LOOP_VECTORIZE`, `NUMBA_SLP_VECTORIZE` | `0` | SIMD de Numba en el backend CPU (ver más abajo). |
| `GPU_MEMORY_FRACTION`, `OPENCL_MEMORY_FRACTION`, `OPENCL_DEVICE`, `CUDA_HOST_COMPILER_DIR`, `CUDA_NVCC_OPTIONS` | ver `env.example` | Backends GPU (ver "Instalación de los backends GPU"). |

`frontend/env.example`:

| Variable | Por defecto | Para qué |
| --- | --- | --- |
| `VITE_BACKEND_URL` | `http://127.0.0.1:8000` | URL del backend; tiene que coincidir con `MOSAIC_HOST` y `MOSAIC_PORT`. |
| `FRONTEND_PORT` | `5173` | Puerto del servidor de Vite (escucha solo en `127.0.0.1`); el origen resultante tiene que coincidir con `MOSAIC_FRONTEND_ORIGIN`. |

### Recorrido por la interfaz

Es una sola pantalla: arriba, el stepper (en pantallas angostas se compacta a "Paso N de 3 · Nombre"); no hay menú ni barra lateral.

1. **Imágenes.** Se elige el lote de teselas (varias imágenes JPEG, PNG o WebP, o un único `.zip`, que puede tener carpetas) y la imagen objetivo. Cada una se sube apenas se elige, con barra de progreso; se ve el resumen ("200 teselas · 4 archivos ignorados"), una muestra de miniaturas y la miniatura del objetivo. Los archivos que no son imágenes (y los `__MACOSX/._*`) se ignoran; las entradas de zip con rutas peligrosas se rechazan.
2. **Parámetros.** Columnas de la grilla, resolución de cada tesela (16, 32 o 64 px), opacidad de las teselas (0–100 %, el `alpha` del algoritmo) y semilla; cada uno tiene un "?" con una explicación. Abajo se recalcula la información del problema: N, M (filas × columnas), M·N y el tamaño de la imagen final. Si la imagen final supera el límite, no se puede avanzar. `k` no se muestra: el servidor usa `min(5, N)`.
3. **Ejecución.** "CPU" o "GPU — <API> (<placa>)": la API (CUDA u OpenCL) la elige el sistema según el hardware; sin GPU la opción aparece deshabilitada con el motivo. Con CPU se muestra el tiempo estimado (calibrado al arrancar el worker) y, si supera el umbral, se pide confirmación.
4. **Progreso.** Una barra por etapa (carga común, preparación de teselas, descriptores del objetivo, matching + top-k, composición y guardado), en vivo por WebSocket. Si se recarga la página, se recupera el trabajo en curso. Mientras dura, ninguna pestaña puede lanzar otro trabajo.
5. **Resultado.** El mosaico sobre un bloque oscuro, con zoom (rueda o botones) y arrastre; "Descargar" en PNG o JPEG con la resolución completa; "Ver estadísticas" con la tabla de tiempos por etapa (las transferencias dicen "no aplica" en CPU) y "Volver a empezar", que regresa al paso 1 con el lote y el objetivo ya cargados (y los últimos parámetros): se puede cambiar solo uno de los dos, y si no se toca el lote la carga común se reutiliza ("reutilizada" en las estadísticas).

Ejemplo real en la máquina de desarrollo (RTX 2080 SUPER, Ryzen), 8.000 teselas, 400 × 300 celdas (960 millones de comparaciones), `tile_px` = 16: CPU 65,97 s en total (matching 64,95 s; estimación previa "~1 min"), GPU (CUDA) 1,19 s con la carga común reutilizada.

## Arquitectura de procesos

```
start.sh / start.ps1
 ├─ backend: python -m app.main  (uvicorn, un solo proceso, sin --reload)
 │   ├─ proceso web (FastAPI): subidas, validación, estado, WebSocket. No hace cómputo.
 │   │   ├─ hilo lector de event_q ──call_soon_threadsafe──▶ event loop ──▶ ProgressHub ──▶ pestañas
 │   │   └─ hilo monitor del worker (process.sentinel): si muere, "el worker se detuvo inesperadamente" y se relanza
 │   └─ proceso worker (spawn): único dueño de los contextos CUDA/OpenCL
 │       ├─ hilo de órdenes: lee command_q, rechaza un segundo RunJob
 │       ├─ hilo de trabajo: detect_and_warmup → calibración CPU → JobRunner (un trabajo a la vez)
 │       └─ pool de decodificación (spawn, N procesos) → memoria compartida
 └─ frontend: npm run dev (servidor de Vite; solo sirve la interfaz)
```

- Por las colas viajan solo dataclasses chicas (`app/worker/messages.py`): ids, rutas, parámetros, progreso, tiempos. Nunca arrays: el worker guarda PNG, JPEG y la vista previa en `MOSAIC_TEMP_DIR/jobs/<id>/<backend>/` (fuera de la medición) y el proceso web los sirve por ruta.
- Todos los procesos hijos se crean con `spawn` (CUDA no sobrevive a un `fork`), por eso `app/main.py` arranca uvicorn dentro de `if __name__ == "__main__":`.
- Ctrl+C llega a todo el grupo de procesos (también en Windows): el worker y su pool ignoran `SIGINT`/`SIGBREAK` y solo terminan con la orden `Shutdown` (o con `terminate()` pasado el tiempo límite).
- El backend conserva solo el último trabajo: si una pestaña muestra un resultado y otra lanza un trabajo nuevo, la primera avisa que ese resultado ya no está disponible.

API del proceso web: `GET /api/state`, `POST /api/tiles` (multipart `files` o `zip`), `GET /api/tiles/{id}`, `GET /api/tiles/{id}/samples/{i}`, `POST /api/targets` (multipart `file`), `GET /api/targets/{id}/image`, `POST /api/jobs` (JSON; 409 si hay un trabajo en curso), `GET /api/jobs/{id}/{backend}/{preview|png|jpg}` y `WS /ws`. El contrato JSON está en `frontend/src/api/types.ts`.

## Estructura

```
TP-Integrador/
├── README.md
├── .venv/                  # entorno virtual del proyecto (no se versiona)
├── start.sh / start.ps1    # instalan lo que falte y levantan backend y frontend
├── backend/                # Python: núcleo, carga, backends, worker y proceso web
│   ├── Makefile            # build / test / lint / format / run / clean
│   ├── pyproject.toml      # configuración de ruff (2 espacios) y pytest
│   ├── requirements.txt    # base: numpy, numba, pillow, fastapi, uvicorn, python-multipart, python-dotenv
│   ├── requirements-cuda.txt   # base + pycuda (GPU NVIDIA)
│   ├── requirements-opencl.txt # base + pyopencl (GPU AMD, NVIDIA, Intel o Apple)
│   ├── requirements-dev.txt # pytest, ruff, httpx
│   ├── env.example         # plantilla de variables de entorno
│   ├── kernels/
│   │   ├── mosaic.cu       # kernels CUDA C
│   │   └── mosaic.cl       # los mismos kernels en OpenCL C
│   ├── app/
│   │   ├── main.py         # punto de entrada: python -m app.main (uvicorn)
│   │   ├── config.py       # variables MOSAIC_* y .env
│   │   ├── worker/         # proceso worker: mensajes, JobRunner, guardado de resultados
│   │   ├── web/            # proceso web: API, WebSocket (ProgressHub), subidas, trabajos, WorkerClient
│   │   ├── core/           # constantes, parámetros, color, contrato de backend, tiempos, choice
│   │   ├── loading/        # decodificación en pool de procesos, objetivo, cache de la última carga
│   │   └── backends/
│   │       ├── cpu/        # backend CPU secuencial (Numba, un hilo, sin SIMD) y su calibración
│   │       ├── cuda/       # backend CUDA (PyCUDA): backend, eventos, búsqueda de cl.exe en Windows
│   │       ├── opencl/     # backend OpenCL (PyOpenCL): backend, profiling, selección de GPU
│   │       ├── gpu_base.py # pasos comunes de CUDA y OpenCL (mismos kernels, grillas y orden)
│   │       ├── kernel_build.py # constantes de Python → -D de los kernels
│   │       └── registry.py # detección, estado, selección y GPU preferida
│   └── tests/
└── frontend/               # React + Vite + TypeScript
    ├── DESIGN.md           # design system de referencia
    ├── env.example         # VITE_BACKEND_URL, FRONTEND_PORT
    └── src/                # api/ (cliente y WebSocket), wizard/ (stepper), steps/, run/, result/, components/, styles/
```

`backend/` y `frontend/` están desacoplados: cada uno tiene sus dependencias, sus tests y su `env.example`, y se comunican solo por HTTP y WebSocket.

## Instalación (solo CPU)

Hace falta Python 3.11 o superior (se desarrolla con 3.13). Todas las dependencias van al entorno virtual `TP-Integrador/.venv`, nunca al Python del sistema. Los comandos se corren desde `TP-Integrador/`.

Linux / macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
```

Windows (PowerShell o Git Bash):

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r backend\requirements-dev.txt
```

Las variables de entorno del backend están documentadas en `backend/env.example`. Ninguna es obligatoria: el backend CPU fija por su cuenta las de Numba (ver más abajo) y las de GPU tienen valores por defecto. Las de GPU se leen al importar `app/core/constants.py`; `python -m app.main` carga `backend/.env` antes de lanzar el worker, así que alcanza con ponerlas ahí.

## Instalación de los backends GPU (opcional)

Sin estas dependencias todo sigue funcionando solo con CPU: los backends GPU se informan como "no disponible (biblioteca no instalada)" y sus tests se saltean con ese motivo. Cada archivo de requisitos incluye el base.

### NVIDIA (CUDA y OpenCL)

1. Driver NVIDIA actualizado (trae también OpenCL).
2. [CUDA Toolkit](https://developer.nvidia.com/cuda-downloads) con `nvcc` en el PATH (`nvcc --version`). PyCUDA compila `kernels/mosaic.cu` con `nvcc` la primera vez y guarda el binario en su cache.
3. **Windows:** `nvcc` necesita el compilador de C++ de Visual Studio (`cl.exe`), que normalmente no está en el PATH. Hay que tener Visual Studio (o las *Build Tools*) con la carga de trabajo "Desarrollo para el escritorio con C++". El backend busca `cl.exe` solo (con `vswhere.exe` y, si no, en las carpetas estándar de Visual Studio, eligiendo la versión de MSVC más alta) y se lo pasa a nvcc con `-ccbin`. Si no lo encuentra, CUDA queda "no disponible (error de compilación de kernels)" y el log dice qué falta; la carpeta se puede indicar a mano con `CUDA_HOST_COMPILER_DIR`. Si el Visual Studio es más nuevo que el que soporta el CUDA Toolkit: `CUDA_NVCC_OPTIONS=-allow-unsupported-compiler`.
4. Instalar, desde `TP-Integrador/`:

   ```powershell
   .venv\Scripts\python.exe -m pip install -r backend\requirements-cuda.txt -r backend\requirements-opencl.txt
   ```

   En Linux: `.venv/bin/python -m pip install -r backend/requirements-cuda.txt -r backend/requirements-opencl.txt`.

### AMD (OpenCL)

1. Driver con OpenCL: Adrenalin en Windows; en Linux, [ROCm](https://rocm.docs.amd.com/) (o el paquete `rocm-opencl-runtime` de la distribución).
2. Instalar `backend/requirements-opencl.txt` en el `.venv` (mismo comando que arriba, sin el de CUDA).

CUDA no aplica: queda "no disponible" y la GPU preferida es OpenCL.

### macOS

Apple trae OpenCL 1.2 (deprecado, pero sirve para desarrollar): `.venv/bin/python -m pip install -r backend/requirements-opencl.txt`. CUDA no existe en macOS.

### Diagnóstico de backends

Desde `backend/` (o `make backends`):

```powershell
..\.venv\Scripts\python.exe -m app.backends.registry
```

Crea y precalienta cada backend (compila los kernels y corre un trabajo mínimo) e imprime su estado. Ejemplo en la máquina donde se desarrolló este cambio (Windows 11, RTX 2080 SUPER y la Radeon integrada de un Ryzen):

```
CPU secuencial: siempre disponible (AMD64 Family 26 Model 68 Stepping 0, AuthenticAMD)
  inicialización: 2384.7 ms
CUDA: NVIDIA GeForce RTX 2080 SUPER
  inicialización: 1357.6 ms
  advertencia: float32 con FMA y funciones matemáticas del driver: puede diferir de CPU en casi-empates
OpenCL: AMD Radeon(TM) Graphics (gfx1036)
  inicialización: 24.6 ms
  advertencia: float32 con FMA y funciones matemáticas del driver: puede diferir de CPU en casi-empates
GPU preferida: CUDA: NVIDIA GeForce RTX 2080 SUPER
```

Sin bibliotecas de GPU se ve `CUDA: no disponible (biblioteca no instalada)`. Otros motivos posibles: `sin dispositivos CUDA`, `sin GPU OpenCL`, `error de compilación de kernels` (el log trae el build log completo) y `error de driver`. OpenCL prioriza las GPUs AMD: en una máquina con una NVIDIA y una Radeon integrada elige la integrada. Para comparar CUDA y OpenCL **sobre la misma placa** se exporta `OPENCL_DEVICE=NVIDIA`.

## Tests, lint y build

Con `make`, desde `TP-Integrador/backend/`:

```bash
make build   # compila a bytecode (detecta errores de sintaxis)
make test    # pytest
make lint    # ruff check + ruff format --check
make lint-kernels  # clang-format --dry-run --Werror sobre kernels/ (Allman, .clang-format del repo)
make backends      # diagnóstico de backends
make run     # levanta el backend (proceso web + worker)
make format  # aplica el formato
make clean   # borra cachés
```

Sin `make` (por ejemplo en Windows), los equivalentes desde `TP-Integrador/backend/` son:

```powershell
..\.venv\Scripts\python.exe -m compileall -q app tests   # build
..\.venv\Scripts\python.exe -m pytest                    # test
..\.venv\Scripts\python.exe -m ruff check .              # lint
..\.venv\Scripts\python.exe -m ruff format --check .     # lint (formato)
..\.venv\Scripts\python.exe -m app.main                  # run
```

En Linux/macOS, reemplazar `..\.venv\Scripts\python.exe` por `../.venv/bin/python`.

### Tests de equivalencia CPU vs CUDA vs OpenCL

`tests/test_backend_equivalence.py` corre cada backend GPU que detecta el registro contra el CPU, sobre lotes sintéticos: N y M no múltiplos de 16, N < 128 con k = 16, teselas duplicadas (empates, también entre hilos distintos de `topk_rows`), `tile_px` ∈ {16, 32, 64}, `k` ∈ {1, 5, 16}, `alpha` ∈ {1; 0,5; 0} y bloque de matching forzado a 16 celdas. Compara descriptores, `topk_idx` (al menos 99 % de las celdas), `topk_dist` e imagen (a lo sumo 1 nivel por canal) con las tolerancias de `app/core/constants.py`.

```powershell
..\.venv\Scripts\python.exe -m pytest tests/test_backend_equivalence.py -rs   # -rs muestra el motivo de cada skip
$env:OPENCL_DEVICE = "NVIDIA"; ..\.venv\Scripts\python.exe -m pytest tests/test_backend_equivalence.py   # OpenCL sobre la NVIDIA
```

Los backends no disponibles aparecen como `SKIPPED ... CUDA no disponible: biblioteca no instalada` (o el motivo que corresponda). En la máquina de desarrollo de este cambio (Windows 11, RTX 2080 SUPER, CUDA 13.4, Visual Studio 2026) corren CPU, CUDA y OpenCL, este último sobre la Radeon integrada y, con `OPENCL_DEVICE=NVIDIA`, sobre la RTX.

## El algoritmo

Lo resuelven igual los tres backends; la definición completa está en `openspec/specs/algoritmo-fotomosaico/spec.md`.

1. **Carga (etapa común, no se compara).** Cada imagen del lote se decodifica, se le aplica la orientación EXIF, se pasa a RGB, se recorta el cuadrado central y se lleva a 128×128 (`tiles_src [N, 128, 128, 3]`). La imagen objetivo se lleva a `(cols·8) × (rows·8)` con `rows = max(1, round(cols · alto / ancho))`. La decodificación de teselas corre en un pool de procesos que escriben directamente en memoria compartida; si se repite el mismo lote se reutiliza la última carga.
2. **Preparación de teselas.** Cada tesela se reduce a `tile_px × tile_px` (16, 32 o 64) promediando bloques con redondeo, y se calcula su descriptor: una miniatura de 8×8 en CIELAB (promedio sRGB de cada bloque de 16×16 convertido a Lab), 192 floats.
3. **Descriptores del objetivo.** Cada celda es un bloque 8×8 de la imagen objetivo; su descriptor son sus 64 píxeles en Lab.
4. **Matching + top-k.** Distancia euclídea al cuadrado `(‖c‖² + ‖t‖²) − 2·c·t` entre cada celda y cada tesela, por bloques de celdas para acotar la memoria. Para cada celda se guardan las `k` teselas más cercanas; ante empate gana el índice menor.
5. **Composición.** Cada celda recibe `topk_idx[celda, choice[celda]]`, donde `choice` es un sorteo reproducible (semilla) generado una vez por trabajo. Si `alpha < 1`, la tesela se mezcla con el color del objetivo: `round(alpha·tesela + (1 − alpha)·objetivo)`.

Ejemplo mínimo de uso desde Python (desde `backend/`):

```python
from app.backends.cpu.backend import CpuBackend
from app.core.choice import generate_choice
from app.core.params import MosaicParams
from app.loading.cache import LoadCache
from app.loading.tile_loader import TileLoader

with TileLoader() as tile_loader:
  loaded = LoadCache(tile_loader).load("ruta/a/teselas", "ruta/a/objetivo.jpg", cols=80)
params = MosaicParams(cols=80, tile_px=32, k=5, alpha=0.8, seed=42)
choice = generate_choice(params.seed, params.k, loaded.target.rows * params.cols)
backend = CpuBackend()
backend.warmup()  # compilación JIT: se mide aparte y no cuenta en el trabajo
result = backend.run(loaded.tiles.tiles_src, loaded.target.target_src, params, choice)
print(result.timings.to_dict())
```

Si se usa desde un script, el código que crea el `TileLoader` tiene que estar bajo `if __name__ == "__main__":`, porque el pool usa `spawn`.

Para usar una GPU, en lugar de crear el backend a mano se usa el registro, que detecta y precalienta todos y libera los contextos al salir del `with`:

```python
from app.backends.registry import BackendRegistry

with BackendRegistry() as registry:
  registry.detect_and_warmup()
  preference = registry.preferred_gpu()  # CUDA si hay, si no OpenCL; .reason si no hay ninguna
  (backend,) = registry.resolve([preference.status.name])  # o resolve(["cpu"]), resolve(["opencl"])...
  result = backend.run(loaded.tiles.tiles_src, loaded.target.target_src, params, choice)
```

## Backend CPU secuencial: por qué un hilo y sin SIMD

El backend CPU es la referencia contra la que se comparan las GPU, así que tiene que ser **estrictamente secuencial**:

- Cada etapa es una función compilada con Numba (`@njit`, sin `parallel`) cuyo bucle externo recorre lo mismo que la grilla de hilos del kernel GPU equivalente; un comentario "una iteración = un hilo de `<kernel>`" marca la correspondencia.
- No se usa NumPy vectorizado sobre los pares celda-tesela ni BLAS, porque usan SIMD y varios hilos.
- LLVM (el compilador debajo de Numba) **auto-vectoriza** los bucles simples con instrucciones SIMD. Eso también es paralelismo (de datos), así que `app/backends/cpu/__init__.py` fija `NUMBA_LOOP_VECTORIZE=0` y `NUMBA_SLP_VECTORIZE=0` antes de importar Numba. Un test lo verifica.
- Por eso la CPU parece más lenta que "una CPU normal": es la definición de secuencial que pide el TP. Para experimentar se pueden poner esas variables en `1` (ver `env.example`).

La compilación JIT ocurre en `warmup()`, que se mide como "tiempo de inicialización" y no se suma a ningún trabajo. Las transferencias host↔device se informan como "no aplica".

## Backends GPU: kernels, grillas y medición

Los dos backends GPU ejecutan **los mismos siete kernels** (`kernels/mosaic.cu` y `kernels/mosaic.cl`, gemelos salvo los calificadores de cada API), con las mismas grillas y en el mismo orden: la secuencia de lanzamientos está escrita una sola vez en `app/backends/gpu_base.py` y cada API solo aporta las primitivas (reservar, copiar, lanzar, sincronizar). Las constantes (tamaños, color, bloques) llegan a los kernels como `-D` generados desde `app/core/constants.py` y `app/core/color.py`: los kernels no tienen números mágicos, y un test verifica que cada `-D` coincide con su constante de Python y que ambos archivos tienen las mismas firmas.

| Kernel | Hilo procesa | Bloque / work-group | Grilla / global size |
| --- | --- | --- | --- |
| `resize_tiles` | 1 píxel (3 canales) de `tiles_px` | 256 | `⌈N·tile_px² / 256⌉` |
| `tile_descriptors` | 1 celda 8×8 de una tesela (bloque 16×16 de la fuente) | 256 | `⌈N·64 / 256⌉` |
| `cell_descriptors` | 1 píxel del bloque 8×8 de una celda | 256 | `⌈M·64 / 256⌉` |
| `sq_norms` | 1 vector de 192 | 256 | `⌈n / 256⌉` (teselas y celdas) |
| `distances_tiled` | 1 elemento `[fila, tesela]` del bloque (tiles 16×16 en memoria compartida, padding 17) | 16×16 | `(⌈N/16⌉, ⌈m_chunk/16⌉)` |
| `topk_rows` | porción intercalada de una fila; top-k en registros y merge en árbol en memoria compartida | 128 | `m_chunk` bloques |
| `compose` | 1 píxel (3 canales) de la imagen final | 16×16 | `(⌈W/16⌉, ⌈H/16⌉)`, `W = cols·tile_px`, `H = rows·tile_px` |

En OpenCL el *global size* es bloques × work-group y cada kernel descarta los hilos sobrantes con un `if`, igual que en CUDA. Cada kernel declara su tamaño de bloque (`__launch_bounds__` en CUDA, `reqd_work_group_size` en OpenCL) con la misma constante que usa el host.

Flujo de un trabajo (igual en las dos APIs):

1. Se reservan todos los buffers del dispositivo y se calcula el bloque del matching (`m_chunk`) con la memoria que queda: en CUDA, `GPU_MEMORY_FRACTION` de la memoria libre (`mem_get_info`); en OpenCL, `OPENCL_MEMORY_FRACTION` de la memoria global (o de la libre, si la GPU AMD la informa) menos lo reservado, acotado por la reserva individual máxima. Si ni un bloque de 16 celdas entra, el trabajo falla con "memoria insuficiente" y el backend sigue usable.
2. Las entradas (`tiles_src`, `target_src`, `choice`) se copian a memoria de *staging* del host (page-locked en CUDA, buffers `ALLOC_HOST_PTR` mapeados en OpenCL) y de ahí al dispositivo. Son las únicas copias host → device.
3. Se encolan **todas** las etapas y todos los bloques del matching en un único stream (CUDA) o una única cola en orden (OpenCL), sin esperar entre bloques.
4. Se encola la copia de la imagen final, la única device → host medida.
5. Recién ahí el host espera, en orden, los marcadores que dejó cada aviso de progreso y los reenvía a medida que la GPU avanza (así esperar no deja a la GPU ociosa). Al final sincroniza y toma el tiempo total.
6. Fuera de la medición, copia `topk_idx`/`topk_dist` para validación.

Tiempos: cada etapa se mide con pares de eventos CUDA o con los contadores de profiling de OpenCL (del inicio del primer comando al fin del último). Las transferencias se informan en dos números: `transfer_*` es el DMA (eventos/profiling) y `staging_*` la copia en el host entre los arrays y la memoria de staging (reloj de pared), que deja a la vista el costo de reservar memoria page-locked: el staging se reutiliza entre trabajos, así que el primero paga la reserva. Si no se puede reservar memoria page-locked, CUDA usa memoria paginable y lo informa en `MosaicResult.notes` ("transferencia sin memoria pinned").

Tiempos ilustrativos (un trabajo sintético después del warmup y de un trabajo previo igual; N = 2.000 teselas, M = 100 × 150 = 15.000 celdas, `tile_px` = 32, k = 5; en ms):

| Backend | Dispositivo | Prep. teselas | Desc. objetivo | Matching | Composición | H→D (DMA) | D→H (DMA) | Total |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CPU secuencial | Ryzen (1 hilo, sin SIMD) | 74,7 | 71,5 | 2.030,3 | 93,7 | no aplica | no aplica | 2.270,3 |
| CUDA | RTX 2080 SUPER | 1,30 | 0,17 | 12,70 | 0,49 | 7,74 | 3,63 | 37,8 |
| OpenCL | RTX 2080 SUPER | 1,53 | 0,16 | 16,64 | 1,17 | 1,35 | 0,26 | 41,3 |
| OpenCL | Radeon integrada (gfx1036) | 14,23 | 3,70 | 303,79 | 15,80 | 3,20 | 1,43 | 404,8 |

No es un benchmark (eso llega en el cambio 5): son corridas sueltas, el total de GPU incluye reservas y staging, y para problemas chicos la GPU puede no ganar.

## Precisión numérica esperada

Los tres backends trabajan en `float32` con las funciones matemáticas estándar de cada plataforma. Por eso los resultados **no son idénticos bit a bit**: las bibliotecas matemáticas de CUDA, de cada driver OpenCL y de LLVM pueden diferir en el último dígito, las GPU fusionan `a*b + c` (FMA) y el orden de las sumas puede cambiar. Eso solo cambia el resultado en casi-empates (dos teselas a distancias casi iguales de una celda).

En la práctica, en la máquina de desarrollo, CUDA y OpenCL coinciden con CPU en todas las celdas de los tests (y en 14.999 de 15.000 en el ejemplo de tiempos, con OpenCL sobre la RTX). En consecuencia, la equivalencia entre backends se verifica con tolerancia (`EQUIVALENCE_LAB_TOLERANCE` para descriptores, `EQUIVALENCE_DIST_RELATIVE_TOLERANCE` para `topk_dist`) y exigiendo que `topk_idx` coincida en al menos `MIN_MATCHING_CELLS_RATIO` (99 %) de las celdas; todas están en `app/core/constants.py`. Cada backend, en cambio, es reproducible consigo mismo: el desempate por índice menor y la semilla de `choice` dan siempre el mismo resultado.

## Patrones de diseño

| Patrón | Dónde | Por qué |
| --- | --- | --- |
| Strategy | `MosaicBackend` (CPU, CUDA y OpenCL) y `StageTimer` (`PerfCounterTimer`, `CudaEventTimer`, `OpenClProfilingTimer`) | El algoritmo es el mismo; cambia cómo se ejecuta y cómo se mide. |
| Template Method | `BaseBackend.run()` en `app/core/backend.py`, y un segundo nivel en `GpuBackend` (`app/backends/gpu_base.py`) | Fija la secuencia de etapas, el cronometraje y el progreso; cada backend implementa solo los pasos, así todos miden exactamente las mismas etapas. `GpuBackend` escribe una sola vez qué kernels se lanzan y con qué grillas; CUDA y OpenCL solo implementan las primitivas de su API. |
| Observer | Callback `on_progress` | El backend no conoce a quién le informa el progreso (un test, el worker, el benchmark). En GPU el aviso se difiere (`DeferredProgressReporter`) hasta que el dispositivo alcanza el marcador encolado. |
| Factory | `app/backends/registry.py` | Una fábrica por backend importa PyCUDA/PyOpenCL recién al crearlo: importar el proyecto nunca falla sin GPU, y una falla de inicialización queda aislada en el estado de ese backend. |
| Productor/Consumidor | `app/loading/tile_loader.py`; colas `command_q`/`event_q` entre web y worker; cola interna del worker | El proceso padre reparte tareas (ruta, índice) y los procesos del pool las consumen escribiendo en memoria compartida. La web produce órdenes que consume el worker y el worker produce eventos que consume el hilo lector de la web; dentro del worker, el hilo de órdenes le pasa los trabajos aceptados al hilo de trabajo. |
| Command | `RunJob` y `Shutdown` en `app/worker/messages.py` | Cada orden es un objeto autocontenido y serializable: el worker la ejecuta sin conocer al proceso web, y `RunJob` ya lleva una lista de backends para que el modo comparación no cambie el protocolo. |
| Observer (eventos) | `ProgressHub` (`app/web/hub.py`); `api/socket.ts` + `useServerState` en el frontend | Cada evento del worker se retransmite a todas las pestañas conectadas; una pestaña nueva recibe primero el estado completo y después los eventos. El frontend se suscribe al WebSocket y aplica cada evento sobre su snapshot. |
| Facade | `WorkerClient` (`app/web/worker_client.py`); `api/client.ts` | El resto del proceso web solo ve `start`/`send`/`stop`: proceso, colas, hilos, monitor y relanzamiento quedan ocultos. Del lado del frontend, ningún componente arma URLs ni maneja fetch/XHR. |
| State | `wizard/wizardReducer.ts` | El stepper es una máquina de estados (`images → params → execution → running → result`) con todas las transiciones en un reducer puro, testeado sin DOM. |

No se usa Singleton: el único recurso global (el contexto de GPU) lo crea explícitamente el backend CUDA (`make_context`, sin `pycuda.autoinit`) en el proceso que lo usa, lo activa solo durante cada operación y lo libera en `close()`; el registro cierra todos los backends al terminar. Ese proceso es el worker: el proceso web nunca importa PyCUDA ni PyOpenCL.
