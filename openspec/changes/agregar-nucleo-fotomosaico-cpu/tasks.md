# Tasks

## 1. Estructura del proyecto

- [ ] 1.1 Crear `TP-Integrador/backend/` con los paquetes `app/core`, `app/loading`, `app/backends/cpu` y `tests/` según design D2, y borrar el placeholder `TP-Integrador/file`; verificar con `python -c "import app.core, app.loading, app.backends.cpu"` desde `TP-Integrador/backend/`.
- [ ] 1.2 Agregar `backend/requirements.txt` (numpy, numba, pillow) y `backend/requirements-dev.txt` (pytest, ruff); verificar que `pip install -r requirements-dev.txt -r requirements.txt` termina sin errores en un venv limpio creado en `TP-Integrador/.venv`.
- [ ] 1.3 Agregar `backend/pyproject.toml` con ruff (`indent-width = 2`) y pytest, `.gitignore` en `TP-Integrador/` (`.env`, `__pycache__`, `.venv`, temporales) y `backend/env.example` con `NUMBA_LOOP_VECTORIZE=0` y `NUMBA_SLP_VECTORIZE=0`; verificar que `ruff check .` y `ruff format --check .` pasan sobre el esqueleto.
- [ ] 1.4 Agregar `backend/Makefile` con `build` (compileall), `test`, `lint` y `clean`, con equivalentes sin `make` en el README; verificar que `make build test` corre (aunque todavía no haya tests).

## 2. Núcleo: constantes, parámetros, color y contrato

- [ ] 2.1 Implementar `app/core/constants.py` con todas las constantes del algoritmo (128, 8, 192, tile_px permitidos, rango de k, tolerancias de equivalencia, etc.); verificar con `ruff` y una revisión de que ningún otro módulo usa esos literales.
- [ ] 2.2 Implementar `MosaicParams` con validación y derivación de `rows` en `app/core/params.py`; verificar con `tests/test_params.py` (tile_px inválido, k > N, α fuera de rango, objetivo 4:3 y objetivo muy apaisado con `rows = 1`).
- [ ] 2.3 Implementar `app/core/color.py`: matriz sRGB→XYZ, blanco D65, constantes de `f(t)` y una conversión de referencia en float64; verificar con `tests/test_color.py` contra blanco, negro, rojo, verde, azul y un gris medio con valores de referencia publicados.
- [ ] 2.4 Implementar `MosaicResult`, `StageTimings` (con "no aplica" para transferencias) y el `StageTimer` basado en `time.perf_counter`; verificar con un test que el total es mayor o igual a la suma de etapas y que las transferencias se serializan como "no aplica".
- [ ] 2.5 Implementar el `Protocol MosaicBackend` y `BaseBackend.run()` (Template Method: etapas, cronometraje, progreso) en `app/core/backend.py`; verificar con un test que usa un backend falso y comprueba el orden de etapas y las llamadas a `on_progress`.
- [ ] 2.6 Implementar `app/core/choice.py` (`np.random.default_rng(seed).integers(0, k, M, dtype=int32)`); verificar con un test de reproducibilidad por semilla y `k = 1 → todo cero`.

## 3. Carga común

- [ ] 3.1 Implementar `app/loading/decode.py` (abrir, `ImageOps.exif_transpose`, RGB, recorte central, `LANCZOS` a 128×128); verificar con `tests/test_loading.py` usando imágenes generadas en el test: apaisada 400×200, EXIF orientación 6, RGBA y escala de grises.
- [ ] 3.2 Implementar `app/loading/tile_loader.py` con pool `spawn`, `SharedMemory` preasignado, orden lexicográfico de rutas relativas y compactación de inválidos; verificar con tests de igualdad byte a byte entre 1 y 4 procesos, archivo corrupto omitido e informado, y lote sin teselas válidas que falla.
- [ ] 3.3 Implementar `app/loading/target_loader.py` (EXIF, RGB, `rows`, resize a `(cols·8, rows·8)`); verificar con tests de forma de `target_src` para 4000×3000 con `cols = 100`.
- [ ] 3.4 Implementar `app/loading/cache.py` (última carga, clave por huella del lote y `cols`) y la medición del tiempo de carga; verificar con tests de que una segunda carga igual no decodifica y se marca como reutilizada, y que cambiar `cols` solo recarga el objetivo.

## 4. Backend CPU secuencial

- [ ] 4.1 Crear `app/backends/cpu/__init__.py` que fija `NUMBA_LOOP_VECTORIZE=0` y `NUMBA_SLP_VECTORIZE=0` antes de importar Numba; verificar con un test que lee `numba.config.LOOP_VECTORIZE` y `SLP_VECTORIZE`.
- [ ] 4.2 Implementar en `stages.py` `resize_tiles` (promedio redondeado) y `compose` (mezcla α en float con redondeo) con comentarios "iteración = hilo"; verificar con `tests/test_algorithm_rules.py` (bloque uniforme, redondeo `0,1,1,1 → 1`, α = 1 copia exacta, α = 0 objetivo ampliado, α = 0,5 → 150).
- [ ] 4.3 Implementar `srgb_to_lab` (con `np.power` y `np.cbrt` en float32) como `@njit(inline="always")` y los kernels `tile_descriptors` (promedio sRGB del bloque 16×16 y conversión) y `cell_descriptors`; verificar que los descriptores coinciden con la conversión de referencia de `color.py` con tolerancia 1e-3 y que una tesela uniforme roja da 64 veces el Lab del rojo.
- [ ] 4.4 Implementar `sq_norms`, `distances` (`(‖c‖² + ‖t‖²) − 2·c·t`) y `topk_rows` con inserción ordenada y desempate por índice; verificar con tests de empate exacto (3 antes que 7), lote de teselas idénticas (`[0, 1, 2, 3]`) e inserción en el medio.
- [ ] 4.5 Implementar `CpuBackend` (warmup que compila con datos mínimos y mide la inicialización, bucle de bloques en Python con progreso, tiempos con `perf_counter`); verificar con `tests/test_cpu_backend.py` que un trabajo sintético con colores sólidos asigna a cada celda la tesela de su color, que el resultado es idéntico con bloques de 16 celdas y con un único bloque, y que el primer trabajo después de `warmup()` no incluye compilación.
- [ ] 4.6 Agregar un test de "un solo hilo" que ejecuta un trabajo mediano y verifica con `threading.active_count()` y la configuración de Numba que no hay paralelismo; documentar en el README por qué el backend desactiva SIMD.

## 5. Documentación

- [ ] 5.1 Escribir el README base de `TP-Integrador/` (objetivo didáctico, estructura `backend/` + `frontend/`, instalación solo CPU en `TP-Integrador/.venv`, cómo correr los tests, algoritmo y la precisión numérica esperada (design D3), patrones de design D6); verificar que los comandos del README funcionan copiados tal cual en un venv limpio.

## Workflow follow-up

- Abrir PR contra `develop` y conseguir las tres aprobaciones que exige el repo.
- Archivar el cambio con `/opsx:archive` antes de aplicar `agregar-backends-gpu`.
