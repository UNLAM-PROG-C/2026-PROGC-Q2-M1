# TP Integrador: generador de fotomosaicos

Un fotomosaico arma una imagen objetivo con una grilla de imágenes chicas (teselas): para cada celda se elige la tesela que más se le parece. El objetivo del TP es **didáctico**: resolver exactamente el mismo problema en paralelo en GPU (CUDA y OpenCL) y secuencialmente en CPU, y mostrar la diferencia de tiempos.

Estado actual (cambio 1 de 5, `agregar-nucleo-fotomosaico-cpu`): carga común de imágenes, definición del algoritmo, contrato común de backends y **backend CPU secuencial**. Los backends GPU, el worker, la interfaz web, el modo comparación y el benchmark llegan en los cambios siguientes (ver `openspec/changes/`).

## Estructura

```
TP-Integrador/
├── README.md
├── .venv/                  # entorno virtual del proyecto (no se versiona)
├── backend/                # Python: núcleo, carga, backends (y más adelante worker y web)
│   ├── Makefile            # build / test / lint / format / clean
│   ├── pyproject.toml      # configuración de ruff (2 espacios) y pytest
│   ├── requirements.txt    # dependencias base: numpy, numba, pillow
│   ├── requirements-dev.txt # pytest, ruff
│   ├── env.example         # plantilla de variables de entorno
│   ├── app/
│   │   ├── core/           # constantes, parámetros, color, contrato de backend, tiempos, choice
│   │   ├── loading/        # decodificación en pool de procesos, objetivo, cache de la última carga
│   │   └── backends/cpu/   # backend CPU secuencial (Numba, un hilo, sin SIMD)
│   └── tests/
└── frontend/               # React + Vite + TypeScript (llega en el cambio 3)
```

`backend/` y `frontend/` están desacoplados: cada uno tiene sus dependencias, sus tests y su `env.example`, y se comunicarán solo por HTTP y WebSocket.

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

Las variables de entorno del backend están documentadas en `backend/env.example`. Hoy ninguna es obligatoria: el backend CPU fija por su cuenta las de Numba (ver más abajo).

## Tests, lint y build

Con `make`, desde `TP-Integrador/backend/`:

```bash
make build   # compila a bytecode (detecta errores de sintaxis)
make test    # pytest
make lint    # ruff check + ruff format --check
make format  # aplica el formato
make clean   # borra cachés
```

Sin `make` (por ejemplo en Windows), los equivalentes desde `TP-Integrador/backend/` son:

```powershell
..\.venv\Scripts\python.exe -m compileall -q app tests   # build
..\.venv\Scripts\python.exe -m pytest                    # test
..\.venv\Scripts\python.exe -m ruff check .              # lint
..\.venv\Scripts\python.exe -m ruff format --check .     # lint (formato)
```

En Linux/macOS, reemplazar `..\.venv\Scripts\python.exe` por `../.venv/bin/python`.

## El algoritmo

Lo resuelven igual los tres backends; la definición completa está en `openspec/changes/agregar-nucleo-fotomosaico-cpu/specs/algoritmo-fotomosaico/spec.md`.

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

## Backend CPU secuencial: por qué un hilo y sin SIMD

El backend CPU es la referencia contra la que se comparan las GPU, así que tiene que ser **estrictamente secuencial**:

- Cada etapa es una función compilada con Numba (`@njit`, sin `parallel`) cuyo bucle externo recorre lo mismo que la grilla de hilos del kernel GPU equivalente; un comentario "una iteración = un hilo de `<kernel>`" marca la correspondencia.
- No se usa NumPy vectorizado sobre los pares celda-tesela ni BLAS, porque usan SIMD y varios hilos.
- LLVM (el compilador debajo de Numba) **auto-vectoriza** los bucles simples con instrucciones SIMD. Eso también es paralelismo (de datos), así que `app/backends/cpu/__init__.py` fija `NUMBA_LOOP_VECTORIZE=0` y `NUMBA_SLP_VECTORIZE=0` antes de importar Numba. Un test lo verifica.
- Por eso la CPU parece más lenta que "una CPU normal": es la definición de secuencial que pide el TP. Para experimentar se pueden poner esas variables en `1` (ver `env.example`).

La compilación JIT ocurre en `warmup()`, que se mide como "tiempo de inicialización" y no se suma a ningún trabajo. Las transferencias host↔device se informan como "no aplica".

## Precisión numérica esperada

Los tres backends trabajan en `float32` con las funciones matemáticas estándar de cada plataforma. Por eso los resultados **no son idénticos bit a bit**: las bibliotecas matemáticas de CUDA, de cada driver OpenCL y de LLVM pueden diferir en el último dígito, las GPU fusionan `a*b + c` (FMA) y el orden de las sumas puede cambiar. Eso solo cambia el resultado en casi-empates (dos teselas a distancias casi iguales de una celda).

En consecuencia, la equivalencia entre backends se verifica con tolerancia (`EQUIVALENCE_LAB_TOLERANCE` para descriptores, `EQUIVALENCE_DIST_RELATIVE_TOLERANCE` para `topk_dist`) y exigiendo que `topk_idx` coincida en al menos `MIN_MATCHING_CELLS_RATIO` (99 %) de las celdas; todas están en `app/core/constants.py`. Cada backend, en cambio, es reproducible consigo mismo: el desempate por índice menor y la semilla de `choice` dan siempre el mismo resultado.

## Patrones de diseño

| Patrón | Dónde | Por qué |
| --- | --- | --- |
| Strategy | `MosaicBackend` (CPU, y luego CUDA y OpenCL) y `StageTimer` (`PerfCounterTimer`; eventos CUDA y profiling OpenCL más adelante) | El algoritmo es el mismo; cambia cómo se ejecuta y cómo se mide. |
| Template Method | `BaseBackend.run()` en `app/core/backend.py` | Fija la secuencia de etapas, el cronometraje y el progreso; cada backend implementa solo los pasos, así todos miden exactamente las mismas etapas. |
| Observer | Callback `on_progress` | El backend no conoce a quién le informa el progreso (un test, el worker, el benchmark). |
| Productor/Consumidor | `app/loading/tile_loader.py` | El proceso padre reparte tareas (ruta, índice) y los procesos del pool las consumen escribiendo en memoria compartida. |

No se usa Singleton: el único recurso global (el contexto de GPU, desde el cambio 2) vive dentro del worker y se pasa explícitamente.
