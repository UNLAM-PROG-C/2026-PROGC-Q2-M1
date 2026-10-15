# Design

## Context

- Parte del diseño general de `agregar-nucleo-fotomosaico-cpu` y de los backends y el registro de `agregar-backends-gpu` (`detect_and_warmup()`, `resolve()`, `close()`).
- Restricciones que vienen de CUDA: el contexto pertenece a un proceso y a un hilo, y no sobrevive a un `fork`. Por eso todo el cómputo vive en un proceso worker con un único hilo de trabajo.
- Una sola persona usa la aplicación en su máquina: no hay autenticación ni colas de trabajos, pero sí puede haber varias pestañas abiertas.

## Goals / Non-Goals

**Goals:**
- Interfaz que no se congela durante trabajos de minutos.
- Protocolo entre procesos chico, tipado y testeable sin GPU.
- Frontend sin frameworks ni build step, que funcione sin internet.

**Non-Goals:**
- Varios usuarios, autenticación, cola de trabajos o cancelación de un trabajo en curso (la cancelación limpia de un kernel de GPU no es trivial; se puede evaluar más adelante).
- Modo comparación (cambio 4).

## Decisions

### D1. Topología y ciclo de vida

```
uvicorn (proceso web, 1 worker, sin --reload)
 ├─ lifespan startup: WorkerClient.start() ──spawn──▶ worker_main()
 │                                                    ├─ registry.detect_and_warmup()
 │                                                    ├─ calibración CPU
 │                                                    ├─ Pool(spawn) de decodificación
 │                                                    └─ bucle: command_q.get() → JobRunner.run()
 ├─ hilo lector de event_q ──▶ asyncio (run_coroutine_threadsafe) ──▶ ProgressHub
 └─ lifespan shutdown: Shutdown → join(timeout) → terminate()
```

- `app/main.py` arranca uvicorn programáticamente dentro de `if __name__ == "__main__":` (obligatorio con `spawn`). `--reload` y varios workers de uvicorn quedan deshabilitados: duplicarían el worker y los contextos de GPU.
- `WorkerClient` (Facade) encapsula colas, proceso y relanzamiento: un monitor revisa `process.sentinel`; si muere, publica `WorkerCrashed`, marca el trabajo fallido y relanza.

### D2. Protocolo de mensajes (Command + Productor/Consumidor)

`app/worker/messages.py` define dataclasses congeladas y serializables con pickle:

| Dirección | Mensaje | Contenido |
| --- | --- | --- |
| web → worker | `RunJob` | `job_id`, directorio de la subida, ruta del objetivo, `MosaicParams`, lista de backends pedidos (o `auto`), directorio de salida |
| web → worker | `Shutdown` | — |
| worker → web | `WorkerReady` | lista de `BackendStatus`, calibración de CPU |
| worker → web | `JobProgress` | `job_id`, backend, etapa, fracción |
| worker → web | `LoadFinished` | tiempo de carga, si se reutilizó, N, archivos omitidos, `rows`, M |
| worker → web | `BackendFinished` | backend, dispositivo, `StageTimings`, rutas PNG/JPEG/preview, dimensiones |
| worker → web | `JobFinished` / `JobFailed` | `job_id` / motivo legible |

Nunca viajan arrays. La lista de backends ya es una lista para que el cambio 4 la reutilice sin cambiar el protocolo.

### D3. Ejecución de un trabajo en el worker

`JobRunner.run(RunJob)`: carga (cache de `app/loading`), genera `choice`, resuelve backend(s) con `registry.resolve()`, ejecuta con `on_progress` → `event_q.put(JobProgress)` (con *throttling* a un mensaje cada `PROGRESS_MIN_INTERVAL_MS`), y **fuera de la medición** guarda PNG (compresión baja para no tardar), JPEG y una vista previa reducida a `PREVIEW_MAX_SIDE`. El guardado en el worker evita que el proceso web tenga que codificar imágenes de cientos de MB.

### D4. Estado del trabajo y API (proceso web)

`JobManager` mantiene `idle | running(job_id, snapshot)` protegido por un `asyncio.Lock`; el snapshot (última etapa y fracción, resultados parciales) permite recuperar el estado al recargar la página.

| Método | Ruta | Uso |
| --- | --- | --- |
| GET | `/` y `/static/*` | interfaz |
| GET | `/api/state` | estado de backends, calibración y trabajo en curso |
| POST | `/api/uploads` | multipart: `tiles[]` o `tiles_zip`, `target` → `upload_id`, N recibidas, ignoradas, dimensiones del objetivo |
| POST | `/api/jobs` | `upload_id`, parámetros, backend → `job_id`; 409 si hay uno en curso, 400/413 si es inválido |
| GET | `/api/jobs/{job_id}/{backend}/{preview,png,jpg}` | resultados |
| WS | `/ws` | eventos; al conectar recibe el snapshot de `/api/state` |

### D5. WebSocket (Observer)

`ProgressHub` guarda las conexiones abiertas y retransmite cada evento del worker a todas. Así una segunda pestaña ve el trabajo en curso y deshabilita su botón (spec `interfaz-web`).

### D6. Subidas

Se escriben en disco por bloques desde `UploadFile` (sin cargar todo en memoria) con límite de bytes total. El zip se extrae entrada por entrada validando con `Path.resolve()` que el destino quede dentro del directorio, ignorando enlaces simbólicos y cortando al superar el tamaño descomprimido o la cantidad de entradas. Directorio base: `MOSAIC_TEMP_DIR` o `tempfile.gettempdir()/fotomosaico`, que se vacía al arrancar y al apagar.

### D7. Estimación de CPU

Al terminar el `warmup()` de CPU, el worker ejecuta las etapas sobre un problema sintético fijo y obtiene costos unitarios: ns por par celda-tesela del matching, por píxel de tesela preparada y por píxel compuesto. La estimación es `pares·c_pares + píxeles·c_píxeles`. La función vive en `app/backends/cpu/calibration.py` (no en el worker) para que `benchmark.py` la reutilice. Se calibra en la máquina real en lugar de usar una constante, que no sería portable. Umbral de confirmación: `MOSAIC_CPU_CONFIRM_SECONDS`.

### D8. Frontend

`static/index.html`, `static/styles.css` y módulos ES sin build: `api.js` (fetch), `socket.js` (WebSocket con reconexión), `form.js` (parámetros y validación con las mismas reglas que el servidor, servidas por `/api/state`), `problem-info.js`, `progress.js`, `preview.js` (zoom con rueda y arrastre sobre la vista previa; al superar cierto zoom carga el PNG completo) y `timings.js`. Sin dependencias de CDN: lo que haga falta se guarda en `static/vendor/` para que funcione sin internet.

### D9. Configuración

`app/config.py` lee variables de entorno (y un `.env` local opcional con `python-dotenv`) con valores por defecto: `MOSAIC_HOST=127.0.0.1`, `MOSAIC_PORT`, `MOSAIC_TEMP_DIR`, `MOSAIC_MAX_UPLOAD_MB`, `MOSAIC_MAX_ZIP_ENTRIES`, `MOSAIC_MAX_OUTPUT_PIXELS`, `MOSAIC_PREVIEW_MAX_SIDE`, `MOSAIC_CPU_CONFIRM_SECONDS`, `MOSAIC_DECODE_PROCESSES`, `MOSAIC_SHUTDOWN_TIMEOUT_S`. Todas se agregan a `env.example`.

### D10. Patrones de este cambio

Productor/Consumidor (colas web↔worker), Command (mensajes `RunJob`/`Shutdown`), Observer (`ProgressHub`), Facade (`WorkerClient`). Se documentan en el README junto a los del cambio 1.

## Risks / Trade-offs

- [Codificar el PNG de un mosaico enorme tarda segundos] → Ocurre fuera de la medición y se muestra como "guardando resultado"; compresión PNG baja.
- [El hilo lector de `event_q` bloquea el apagado] → Se le envía un mensaje centinela y se usa `get(timeout=...)`.
- [Muchos mensajes de progreso saturan el WebSocket] → *Throttling* en el worker y solo cambios de fracción significativos.
- [Ctrl+C llega también al worker (mismo grupo de procesos)] → El worker ignora `SIGINT` y solo termina con `Shutdown` o por el `terminate()` del timeout.
- [Sin cancelación, un trabajo de CPU muy largo obliga a esperar] → La estimación con confirmación previa lo mitiga; reiniciar la app es la salida de emergencia.

## Open Questions

- Valores por defecto concretos de los límites (MB de subida, píxeles de salida, umbral de confirmación): se ajustan al probar en las máquinas del grupo, sin cambiar las specs.
