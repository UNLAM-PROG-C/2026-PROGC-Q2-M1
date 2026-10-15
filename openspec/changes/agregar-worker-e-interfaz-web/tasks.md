# Tasks

## 1. Configuración y dependencias

- [ ] 1.1 Agregar `fastapi`, `uvicorn`, `python-multipart` y `python-dotenv` a `requirements.txt` y `httpx` a `requirements-dev.txt`; verificar la instalación en un venv limpio.
- [ ] 1.2 Implementar `app/config.py` con las variables de design D9 y sus valores por defecto, y completar `env.example`; verificar con un test que sin entorno el host es `127.0.0.1` y que una variable sobrescribe su valor.

## 2. Protocolo y worker

- [ ] 2.1 Implementar `app/worker/messages.py` (dataclasses de design D2); verificar con un test que todos los mensajes sobreviven ida y vuelta por `pickle` y que ninguno tiene campos `np.ndarray`.
- [ ] 2.2 Implementar `JobRunner` (carga con cache, `choice`, `resolve()`, progreso con *throttling*, guardado PNG/JPEG/preview fuera de la medición, errores → `JobFailed`); verificar con tests que usan un backend falso y colas en memoria: secuencia de eventos de un trabajo exitoso y de uno que falla.
- [ ] 2.3 Implementar la calibración de CPU de design D7 y su inclusión en `WorkerReady`; verificar con un test que la estimación crece con M·N y que la calibración tarda menos de un tiempo acotado.
- [ ] 2.4 Implementar `worker_main()` (ignora `SIGINT`, `detect_and_warmup()`, calibración, pool `spawn`, bucle de órdenes, rechazo de un `RunJob` concurrente, `Shutdown` que cierra pool y contextos); verificar con un test de integración que lanza el worker real con solo CPU, ejecuta un trabajo sintético y lo apaga sin procesos huérfanos.

## 3. Proceso web

- [ ] 3.1 Implementar `WorkerClient` (Facade: arranque `spawn`, hilo lector de eventos con centinela, monitor de `sentinel`, relanzamiento, apagado con timeout y `terminate()`); verificar con un test que mata el worker y comprueba `WorkerCrashed`, trabajo fallido y relanzamiento.
- [ ] 3.2 Implementar `app/web/uploads.py` (escritura por bloques con límite, filtro por extensión, extracción segura de zip, limpieza de temporales al arrancar, al apagar y al subir de nuevo); verificar con `tests/test_uploads.py`: archivos sueltos, zip con carpetas, `__MACOSX` y `.txt` ignorados, `../../etc/passwd` rechazado, zip excedido → 413 y borrado, `.gif` como objetivo → 400.
- [ ] 3.3 Implementar `JobManager`, `ProgressHub` y las rutas de design D4 con el lifespan de FastAPI; verificar con `tests/test_web_api.py` (TestClient + worker falso): `/api/state`, subida, trabajo aceptado, 409 con un trabajo en curso, rechazo de backend no disponible, rechazo por tamaño de salida, y que dos clientes WebSocket reciben los mismos eventos.
- [ ] 3.4 Implementar `app/main.py` (uvicorn programático, guardia `__main__`, sin reload) y el target `make run`; verificar que `make run` levanta la app en `127.0.0.1` y que Ctrl+C la apaga sin procesos huérfanos (`ps` después de salir).

## 4. Interfaz

- [ ] 4.1 Crear `static/index.html`, `styles.css`, `api.js` y `socket.js` (reconexión y snapshot al conectar); verificar a mano que al recargar durante un trabajo se recupera el progreso.
- [ ] 4.2 Implementar `form.js` (parámetros, validación con reglas de `/api/state`, selector de backend con estados y "Automático", bloqueo durante un trabajo en todas las pestañas) y `problem-info.js` (N, M, M·N, tamaño en px y MB, advertencia de salida gigante, estimación y confirmación de CPU); verificar a mano los escenarios de la spec `interfaz-web` (k = 20, cambio de columnas, dos pestañas, CPU largo).
- [ ] 4.3 Implementar `progress.js` (barra por etapa), `preview.js` (zoom y arrastre, carga del PNG completo al acercar), descargas PNG/JPEG, `timings.js` (tabla con "no aplica" y carga reutilizada) y la visualización de errores; verificar con un trabajo real en CPU y, si hay GPU, con un trabajo GPU, comprobando la tabla y las descargas.

## 5. Documentación e integración

- [ ] 5.1 Documentar en el README cómo ejecutar la aplicación (`make run` y equivalente sin `make`), las variables de `env.example`, un recorrido por la interfaz y los patrones de design D10; verificar siguiendo el README desde cero en la máquina de desarrollo.
- [ ] 5.2 Prueba de punta a punta: subir un zip de ~200 fotos y un objetivo, ejecutar con CPU y con el backend GPU disponible, y repetir para comprobar que la carga se reutiliza; registrar el resultado (capturas y tiempos) en el PR.

## Workflow follow-up

- Requiere archivados `agregar-nucleo-fotomosaico-cpu` y `agregar-backends-gpu`.
- PR contra `develop` con tres aprobaciones; archivar antes de aplicar `agregar-modo-comparacion`.
