# Tasks

## 1. Configuración y dependencias del backend

- [x] 1.1 Agregar `fastapi`, `uvicorn`, `python-multipart` y `python-dotenv` a `backend/requirements.txt` y `httpx` a `backend/requirements-dev.txt`; verificar la instalación en un venv limpio.
- [x] 1.2 Implementar `backend/app/config.py` con las variables de design D10 y sus valores por defecto, y completar `backend/env.example`; verificar con un test que sin entorno el host es `127.0.0.1`, que el origen permitido coincide con el frontend por defecto y que una variable sobrescribe su valor.

## 2. Protocolo y worker

- [x] 2.1 Implementar `app/worker/messages.py` (dataclasses de design D2, con la GPU preferida en `WorkerReady`); verificar con un test que todos los mensajes sobreviven ida y vuelta por `pickle` y que ninguno tiene campos `np.ndarray`.
- [x] 2.2 Implementar `JobRunner` (carga con cache, `choice`, `resolve()`, progreso con *throttling*, guardado PNG/JPEG/preview fuera de la medición, errores → `JobFailed`); verificar con tests que usan un backend falso y colas en memoria: secuencia de eventos de un trabajo exitoso y de uno que falla.
- [x] 2.3 Implementar la calibración de CPU de design D8 en `app/backends/cpu/calibration.py` y su inclusión en `WorkerReady`; verificar con un test que la estimación crece con M·N y que la calibración tarda menos de un tiempo acotado.
- [x] 2.4 Implementar `worker_main()` (ignora `SIGINT`, `detect_and_warmup()`, `preferred_gpu()`, calibración, pool `spawn`, bucle de órdenes, rechazo de un `RunJob` concurrente, `Shutdown` que cierra pool y contextos); verificar con un test de integración que lanza el worker real con solo CPU, ejecuta un trabajo sintético y lo apaga sin procesos huérfanos.

## 3. Proceso web

- [x] 3.1 Implementar `WorkerClient` (Facade: arranque `spawn`, hilo lector de eventos con centinela, monitor de `sentinel`, relanzamiento, apagado con timeout y `terminate()`); verificar con un test que mata el worker y comprueba `WorkerCrashed`, trabajo fallido y relanzamiento.
- [x] 3.2 Implementar `app/web/uploads.py` (lote y objetivo como recursos separados, escritura por bloques con límite, filtro por extensión, extracción segura de zip, muestra de teselas, retención y limpieza de design D7); verificar con `tests/test_uploads.py`: archivos sueltos, zip con carpetas, `__MACOSX` y `.txt` ignorados, `../../etc/passwd` rechazado, zip excedido → 413 y borrado, `.gif` como objetivo → 400, lote nuevo que conserva el último objetivo.
- [x] 3.3 Implementar la traducción de forma de ejecución de design D4 (`cpu`/`gpu` → lista de backends, `k = min(DEFAULT_K, N)`); verificar con tests: `gpu` sin GPU → 400 con motivo, `gpu` con CUDA y OpenCL disponibles → CUDA, `gpu` con solo OpenCL → OpenCL, lote de 3 teselas → `k = 3`.
- [x] 3.4 Implementar `JobManager`, `ProgressHub`, CORS y las rutas de design D5 con el lifespan de FastAPI; verificar con `tests/test_web_api.py` (TestClient + worker falso): `/api/state` con opciones de ejecución y últimas subidas, subidas, trabajo aceptado, 409 con un trabajo en curso, rechazo por tamaño de salida, origen no permitido sin cabeceras CORS y que dos clientes WebSocket reciben los mismos eventos.
- [x] 3.5 Implementar `app/main.py` (uvicorn programático, guardia `__main__`, sin reload) y el target `make run` en `backend/`; verificar que levanta el backend en `127.0.0.1` sin ningún archivo del frontend y que Ctrl+C lo apaga sin procesos huérfanos (`ps` después de salir).

## 4. Frontend

- [x] 4.1 Crear `frontend/` con Vite + React + TypeScript, ESLint (Google TS style, 2 espacios, llaves Allman, `max-len` 180), Vitest y `env.example` (`VITE_BACKEND_URL`, `FRONTEND_PORT`), y mover `design.md` de la raíz del repo a `TP-Integrador/frontend/DESIGN.md`; verificar que `npm run lint`, `npm test` y `npm run build` pasan sobre el esqueleto.
- [x] 4.2 Implementar `styles/tokens.css` y `base.css` con los tokens de `DESIGN.md` (design D12), Inter con `@fontsource/inter`, `stylelint` que prohíbe colores literales fuera de `tokens.css`, y los componentes base `PillButton`, `OptionCard` y `HelpTooltip`; verificar con `npm run lint` que no hay colores literales fuera de los tokens y con tests de Vitest que `HelpTooltip` muestra el texto con `mouseenter` y `focus`, lo oculta con `mouseleave` y Escape, y lo vincula por `aria-describedby`.
- [x] 4.3 Implementar el layout de una sola pantalla: franja fija del stepper con estilo `sub-nav-frosted`, tiles de cada paso y compactación por debajo de 640 px, sin sidebar ni menú global; verificar a mano en 1440, 834 y 400 px de ancho los escenarios "Navegación" y "Pantalla angosta".
- [x] 4.4 Implementar `api/client.ts` (incluido el progreso de subida), `api/socket.ts` (reconexión y snapshot al conectar) y `api/types.ts`; verificar a mano que al recargar durante un trabajo se recupera el progreso.
- [x] 4.5 Implementar el reducer del stepper y `Stepper.tsx` (design D9); verificar con tests de Vitest las transiciones válidas, que "Siguiente" se habilita solo con datos válidos y que `RESTART` conserva `tiles_id`, `target_id`, parámetros y forma de ejecución.
- [x] 4.6 Implementar `ImagesStep` (zonas de carga, subida solo de lo que cambió, resumen y miniaturas, reconstrucción desde `/api/state` tras recargar); verificar a mano los escenarios "Lote subido", "Cambiar solo el objetivo" y "Recarga en la pantalla de resultado".
- [x] 4.7 Implementar `ParamsStep` (columnas, resolución, opacidad 0–100 % → `alpha`, semilla, `HelpTooltip` con los textos de la spec en `steps/paramHelp.ts`, chips de resolución, información del problema, advertencia de salida gigante); verificar con tests que cada parámetro tiene su ayuda, que 60 % envía `alpha = 0.6`, que columnas fuera de rango bloquean "Siguiente" y el escenario "Cambio de columnas".
- [x] 4.8 Implementar `ExecutionStep` (tarjetas CPU y GPU con API y dispositivo, GPU deshabilitada con motivo, estimación y confirmación de CPU, bloqueo durante un trabajo en todas las pestañas); verificar con un test que sin GPU solo CPU es elegible y a mano los escenarios "Trabajo largo en CPU" y "Dos pestañas".
- [x] 4.9 Implementar `ProgressView`, `ResultView`, `MosaicViewer` (zoom y arrastre, carga del PNG completo al acercar), `DownloadMenu` (PNG/JPEG), `StatsPanel` + `TimingsTable` (solo al apretar "Ver estadísticas", "no aplica" y carga reutilizada), "Volver a empezar" y la visualización de errores; con el mosaico sobre tile oscuro y sombra de producto (design D12); verificar con un trabajo real en CPU y, si hay GPU, con uno en GPU, comprobando descargas, estadísticas y que volver a empezar no vuelve a subir las imágenes.

## 5. Script de arranque

- [x] 5.1 Implementar `TP-Integrador/start.sh` según design D11 (Python mínimo, venv, huella de dependencias, detección de NVIDIA con caída a OpenCL, `--cpu-only` y `--reinstall`, Node vía `nodeenv` si falta, `npm ci`, `.env` desde `env.example`, arranque de backend y frontend, Ctrl+C que detiene ambos); verificar en macOS desde un clon limpio (primer arranque), con un segundo arranque sin reinstalaciones y con `PATH` sin `node`.
- [x] 5.2 Implementar `TP-Integrador/start.ps1` con el mismo comportamiento; verificar en Windows (o en la máquina NVIDIA del grupo) el primer arranque, el segundo sin reinstalaciones y la instalación de PyCUDA o la caída a OpenCL.
- [x] 5.3 Agregar `.venv`, `node_modules`, `.env` y los temporales al `.gitignore` de `TP-Integrador/`; verificar con `git status` después de un arranque completo que no aparece nada generado.

## 6. Documentación e integración

- [x] 6.1 Documentar en el README cómo levantar la aplicación con el script (opciones, qué instala y dónde), cómo levantar backend y frontend por separado, las variables de ambos `env.example`, un recorrido por el stepper y los patrones de design D13; verificar siguiendo el README desde cero en la máquina de desarrollo.
- [x] 6.2 Prueba de punta a punta: subir un zip de ~200 fotos y un objetivo, ejecutar en CPU y en GPU, y usar "Volver a empezar" para comprobar que las imágenes quedan cargadas y la carga se reutiliza; registrar el resultado (capturas y tiempos) en el PR.

## Verificación (2026-10-23, Windows 11, RTX 2080 SUPER)

- `start.ps1`, primer arranque: detectó NVIDIA e instaló PyCUDA, usó el Node 24 del `PATH`, corrió `npm ci`, creó ambos `.env` y levantó backend y frontend (CPU, CUDA y OpenCL disponibles). Segundo arranque: sin reinstalaciones ("al día" en Python, GPU y npm). Al detener, no quedaron procesos del backend, el worker ni Vite.
- `git status` limpio después del arranque completo (5.3).
- `start.sh`: sintaxis (`bash -n`), `--help` y opción desconocida verificados; **queda pendiente la prueba en macOS** (clon limpio, segundo arranque y `PATH` sin `node`) en la máquina de un compañero.
- Punta a punta por la API: zip de 200 teselas + 1 archivo ignorado, objetivo 640×480, 100 columnas, `tile_px` 32: CPU 190 ms en total, después GPU (CUDA) 69 ms con la carga común reutilizada; vista previa y PNG descargados. Con 8.000 teselas y 400 × 300 celdas: CPU 65,97 s y CUDA 1,19 s (ver README).

## Workflow follow-up

- Requiere archivados `agregar-nucleo-fotomosaico-cpu` y `agregar-backends-gpu`.
- PR contra `develop` con tres aprobaciones; archivar antes de aplicar `agregar-modo-comparacion`.
