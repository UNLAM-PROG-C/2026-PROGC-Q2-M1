# Design

## Context

- Parte del diseño general de `agregar-nucleo-fotomosaico-cpu` (estructura `backend/` + `frontend/`, design D2) y de los backends y el registro de `agregar-backends-gpu` (`detect_and_warmup()`, `resolve()`, `preferred_gpu()`, `close()`).
- Restricciones que vienen de CUDA: el contexto pertenece a un proceso y a un hilo, y no sobrevive a un `fork`. Por eso todo el cómputo vive en un proceso worker con un único hilo de trabajo.
- Una sola persona usa la aplicación en su máquina: no hay autenticación ni colas de trabajos, pero sí puede haber varias pestañas abiertas.
- La persona que usa la interfaz no tiene por qué saber qué es CUDA u OpenCL: elige "CPU" o "GPU" y el sistema decide la API de GPU según la placa.

## Goals / Non-Goals

**Goals:**
- Backend y frontend desacoplados: carpetas, dependencias y procesos propios, comunicados solo por HTTP y WebSocket.
- Interfaz guiada (stepper) que no se congela durante trabajos de minutos.
- Protocolo entre procesos chico, tipado y testeable sin GPU.
- Un único comando para levantar todo, que instale lo que falte y no reinstale lo que ya está.
- Una vez instalada, la aplicación funciona sin internet (sin CDN).
- Una interfaz de una sola pantalla, sin sidebar, con el lenguaje visual de `frontend/DESIGN.md`.

**Non-Goals:**
- Varios usuarios, autenticación, cola de trabajos o cancelación de un trabajo en curso (la cancelación limpia de un kernel de GPU no es trivial; se puede evaluar más adelante).
- Elegir entre CUDA y OpenCL desde la interfaz: esa comparación queda para `benchmark.py` (cambio 5).
- Ejecución con CPU y GPU a la vez y estadísticas comparativas (cambio 4).
- Build de producción del frontend servido por otro servidor: la aplicación es local y se levanta con el servidor de Vite.

## Decisions

### D1. Topología y ciclo de vida

```
start.sh / start.ps1
 ├─ backend: python -m app.main (uvicorn, 1 worker, sin --reload)
 │   ├─ lifespan startup: WorkerClient.start() ──spawn──▶ worker_main()
 │   │                                                    ├─ registry.detect_and_warmup()
 │   │                                                    ├─ calibración CPU
 │   │                                                    ├─ Pool(spawn) de decodificación
 │   │                                                    └─ bucle: command_q.get() → JobRunner.run()
 │   ├─ hilo lector de event_q ──▶ asyncio (run_coroutine_threadsafe) ──▶ ProgressHub
 │   └─ lifespan shutdown: Shutdown → join(timeout) → terminate()
 └─ frontend: npm run dev (servidor de Vite en 127.0.0.1, sin cómputo)
        navegador ──HTTP/WS──▶ backend (CORS solo para el origen del frontend)
```

- `app/main.py` arranca uvicorn programáticamente dentro de `if __name__ == "__main__":` (obligatorio con `spawn`). `--reload` y varios workers de uvicorn quedan deshabilitados: duplicarían el worker y los contextos de GPU.
- `WorkerClient` (Facade) encapsula colas, proceso y relanzamiento: un monitor revisa `process.sentinel`; si muere, publica `WorkerCrashed`, marca el trabajo fallido y relanza.
- El servidor de Vite es un proceso Node independiente: solo sirve la interfaz y no conoce al worker.

### D2. Protocolo de mensajes (Command + Productor/Consumidor)

`app/worker/messages.py` define dataclasses congeladas y serializables con pickle:

| Dirección | Mensaje | Contenido |
| --- | --- | --- |
| web → worker | `RunJob` | `job_id`, directorio del lote, ruta del objetivo, `MosaicParams`, lista explícita de backends, directorio de salida |
| web → worker | `Shutdown` | — |
| worker → web | `WorkerReady` | lista de `BackendStatus`, GPU preferida (`preferred_gpu()`), calibración de CPU |
| worker → web | `JobProgress` | `job_id`, backend, etapa, fracción |
| worker → web | `LoadFinished` | tiempo de carga, si se reutilizó, N, archivos omitidos, `rows`, M |
| worker → web | `BackendFinished` | backend, dispositivo, `StageTimings`, rutas PNG/JPEG/preview, dimensiones |
| worker → web | `JobFinished` / `JobFailed` | `job_id` / motivo legible |

Nunca viajan arrays. `RunJob` ya lleva una lista de backends para que el cambio 4 ejecute CPU y GPU sin cambiar el protocolo.

### D3. Ejecución de un trabajo en el worker

`JobRunner.run(RunJob)`: carga (cache de `app/loading`), genera `choice`, toma los backends con `registry.resolve()`, ejecuta con `on_progress` → `event_q.put(JobProgress)` (con *throttling* a un mensaje cada `PROGRESS_MIN_INTERVAL_MS`), y **fuera de la medición** guarda PNG (compresión baja para no tardar), JPEG y una vista previa reducida a `PREVIEW_MAX_SIDE`. El guardado en el worker evita que el proceso web tenga que codificar imágenes de cientos de MB.

### D4. Forma de ejecución: CPU o GPU

La interfaz no habla de backends sino de **formas de ejecución**: `cpu` o `gpu` (el cambio 4 agrega `both`).

- El worker publica en `WorkerReady` la GPU preferida que calcula `registry.preferred_gpu()` (cambio 2): CUDA si está disponible (placa NVIDIA con PyCUDA funcionando), si no OpenCL, si no ninguna con el motivo combinado.
- El proceso web traduce la forma a una lista explícita de backends: `cpu → [cpu]`, `gpu → [GPU preferida]`. Si se pide `gpu` sin GPU disponible, rechaza con 400 y el motivo; nunca cae a CPU en silencio.
- `/api/state` expone las opciones ya resueltas, por ejemplo `gpu: {available: true, api: "CUDA", device: "GeForce RTX 3060"}`, para que el paso 3 muestre "GPU — CUDA (GeForce RTX 3060)" sin lógica de selección en el frontend.

### D5. Estado del trabajo y API (proceso web)

`JobManager` mantiene `idle | running(job_id, snapshot)` protegido por un `asyncio.Lock`; el snapshot (última etapa y fracción, resultados parciales) permite recuperar el estado al recargar la página.

| Método | Ruta | Uso |
| --- | --- | --- |
| GET | `/api/state` | backends, opciones de ejecución, calibración, reglas de parámetros, trabajo en curso y últimas subidas (lote y objetivo) |
| POST | `/api/tiles` | multipart: `files[]` o `zip` → `tiles_id`, N aceptadas, ignoradas, rechazadas |
| GET | `/api/tiles/{tiles_id}` | resumen del lote y nombres de una muestra de hasta `MOSAIC_TILE_SAMPLE_COUNT` teselas |
| GET | `/api/tiles/{tiles_id}/samples/{i}` | archivo original de la muestra `i` (el navegador lo escala) |
| POST | `/api/targets` | multipart: `file` → `target_id`, dimensiones |
| GET | `/api/targets/{target_id}/image` | archivo original del objetivo |
| POST | `/api/jobs` | `tiles_id`, `target_id`, `cols`, `tile_px`, `alpha`, `seed`, `mode` → `job_id`; 409 si hay uno en curso, 400/413 si es inválido |
| GET | `/api/jobs/{job_id}/{backend}/{preview,png,jpg}` | resultados |
| WS | `/ws` | eventos; al conectar recibe el snapshot de `/api/state` |

- `k` no viaja desde la interfaz: el servidor usa `k = min(DEFAULT_K, N)`, con `DEFAULT_K` de `app/core/constants.py`, para que un lote chico no quede rechazado por `k > N`.
- CORS (`CORSMiddleware`) permite solo `MOSAIC_FRONTEND_ORIGIN`; el WebSocket valida el mismo origen.
- Los endpoints de muestras y objetivo devuelven el archivo tal como se subió: el proceso web no decodifica imágenes.

### D6. WebSocket (Observer)

`ProgressHub` guarda las conexiones abiertas y retransmite cada evento del worker a todas. Así una segunda pestaña ve el trabajo en curso y deshabilita la ejecución (spec `interfaz-web`).

### D7. Subidas

- Lote y objetivo son recursos separados (`tiles/<id>/`, `targets/<id>/`): "volver a empezar" puede conservar uno y cambiar el otro, y conservar el lote hace que la cache de carga del cambio 1 lo reutilice sin volver a decodificarlo.
- Se escriben en disco por bloques desde `UploadFile` (sin cargar todo en memoria) con límite de bytes total. El zip se extrae entrada por entrada validando con `Path.resolve()` que el destino quede dentro del directorio, ignorando enlaces simbólicos y cortando al superar el tamaño descomprimido o la cantidad de entradas.
- Retención: se conservan el último lote, el último objetivo, los que use un trabajo en curso y los resultados del último trabajo; lo demás se borra al recibir una subida nueva o al empezar un trabajo nuevo.
- Directorio base: `MOSAIC_TEMP_DIR` o `tempfile.gettempdir()/fotomosaico`, que se vacía al arrancar y al apagar.

### D8. Estimación de CPU

Al terminar el `warmup()` de CPU, el worker ejecuta las etapas sobre un problema sintético fijo y obtiene costos unitarios: ns por par celda-tesela del matching, por píxel de tesela preparada y por píxel compuesto. La estimación es `pares·c_pares + píxeles·c_píxeles`. La función vive en `backend/app/backends/cpu/calibration.py` (no en el worker) para que `benchmark.py` la reutilice. Se calibra en la máquina real en lugar de usar una constante, que no sería portable. Umbral de confirmación: `MOSAIC_CPU_CONFIRM_SECONDS`.

### D9. Frontend: React + Vite + TypeScript

```
frontend/
├── package.json / package-lock.json   # scripts: dev, build, lint, test
├── vite.config.ts                     # puerto y host 127.0.0.1 desde el entorno
├── tsconfig.json
├── eslint.config.js                   # Google TS style + llaves Allman
├── env.example                        # VITE_BACKEND_URL, FRONTEND_PORT
├── DESIGN.md                          # design system de referencia (D12)
├── index.html
└── src/
    ├── main.tsx, App.tsx
    ├── styles/       # tokens.css (tokens de DESIGN.md como variables CSS), base.css, componentes
    ├── api/          # client.ts (fetch; XHR para el progreso de subida), socket.ts (reconexión), types.ts (DTOs y eventos)
    ├── wizard/       # wizardReducer.ts (estado del stepper), useWizard.ts, Stepper.tsx
    ├── steps/        # ImagesStep.tsx, ParamsStep.tsx, ExecutionStep.tsx
    ├── run/          # ProgressView.tsx (barra por etapa)
    ├── result/       # ResultView.tsx, MosaicViewer.tsx (zoom), DownloadMenu.tsx, StatsPanel.tsx, TimingsTable.tsx
    └── components/   # FileDropZone.tsx, ImageThumb.tsx, HelpTooltip.tsx, PillButton.tsx, OptionCard.tsx
```

- **Estado del stepper**: un `useReducer` con estados `images → params → execution → running → result` y acciones explícitas (`UPLOAD_DONE`, `JOB_STARTED`, `JOB_FINISHED`, `RESTART`...). Las transiciones válidas viven en un solo lugar y se testean sin DOM. Un paso solo habilita "Siguiente" cuando sus datos son válidos.
- **Paso 1 (imágenes)**: dos zonas para soltar archivos (lote: varios archivos o un zip; objetivo: un archivo). Al avanzar se suben solo los recursos que cambiaron, con barra de progreso de subida; el resumen ("200 teselas, 3 ignoradas") y las miniaturas quedan a la vista.
- **Paso 2 (parámetros)**: "Columnas de la grilla", "Resolución de cada tesela" (16, 32 o 64 px), "Opacidad de las teselas" (`alpha` mostrado como 0–100 %) y "Semilla". Cada etiqueta lleva un `HelpTooltip` (ver abajo) con los textos de la spec `interfaz-web`, que viven en un único módulo `steps/paramHelp.ts`. Debajo, la información del problema (N, M, M·N, tamaño final) recalculada en vivo. Las reglas de validación llegan por `/api/state`, así que no se duplican constantes.
- **Paso 3 (ejecución)**: tarjetas de selección "CPU" y "GPU — <API> (<dispositivo>)" a partir de las opciones de D4; las no disponibles se ven deshabilitadas con el motivo. Con CPU se muestra la estimación de D8 y, si supera el umbral, se pide confirmación al ejecutar.
- **Ejecución y resultado**: `ProgressView` muestra la barra por etapa; al terminar, `ResultView` muestra el mosaico (`MosaicViewer`: zoom con rueda y arrastre sobre la vista previa; pasado cierto zoom carga el PNG completo), el menú de descarga (PNG/JPEG) y el botón "Ver estadísticas", que abre `StatsPanel` con `TimingsTable`. El cambio 4 agrega a `StatsPanel` la vista comparativa.
- **Volver a empezar**: la acción `RESTART` vuelve al paso 1 conservando `tiles_id`, `target_id`, sus resúmenes y miniaturas (y los últimos parámetros y forma de ejecución). Si la página se recargó, las miniaturas se reconstruyen con las últimas subidas que informa `/api/state` y los endpoints de muestras. Cambiar una imagen descarta solo ese recurso.
- **`HelpTooltip`**: botón de 16 px con "?" (círculo `{rounded.full}`, texto `{colors.ink-muted-48}`) con un área táctil de 44 × 44 px. Muestra el texto con `mouseenter`/`focus` y lo oculta con `mouseleave`/`blur`/Escape; en táctil, un toque alterna. El texto va en un elemento con `role="tooltip"` referenciado por `aria-describedby` desde el campo. Sin bibliotecas de tooltips: es un componente chico y propio.
- **Estilo de código**: TypeScript con la Google TypeScript Style Guide, 2 espacios, `max-len` 180 y llaves Allman (`@stylistic/brace-style: allman`) según `CLAUDE.md`. No se usa Prettier porque no admite Allman. Componentes y funciones de menos de ~15 líneas, extrayendo subcomponentes y hooks.
- **Tests**: Vitest + Testing Library para el reducer del stepper, la validación de parámetros y el bloqueo de opciones sin GPU.
- **Sin CDN**: todas las dependencias se instalan con npm y Vite las empaqueta; después de la instalación no hace falta internet.

### D10. Configuración

- Backend: `app/config.py` lee variables de entorno (y un `.env` local opcional con `python-dotenv`) con valores por defecto: `MOSAIC_HOST=127.0.0.1`, `MOSAIC_PORT`, `MOSAIC_FRONTEND_ORIGIN`, `MOSAIC_TEMP_DIR`, `MOSAIC_MAX_UPLOAD_MB`, `MOSAIC_MAX_ZIP_ENTRIES`, `MOSAIC_MAX_OUTPUT_PIXELS`, `MOSAIC_PREVIEW_MAX_SIDE`, `MOSAIC_TILE_SAMPLE_COUNT`, `MOSAIC_CPU_CONFIRM_SECONDS`, `MOSAIC_DECODE_PROCESSES`, `MOSAIC_SHUTDOWN_TIMEOUT_S`. Todas van a `backend/env.example`.
- Frontend: `VITE_BACKEND_URL` y `FRONTEND_PORT` en `frontend/env.example`. El valor por defecto de `MOSAIC_FRONTEND_ORIGIN` coincide con el host y puerto por defecto del frontend.

### D11. Entorno virtual y script de arranque

`TP-Integrador/start.sh` (bash, macOS/Linux) y `TP-Integrador/start.ps1` (PowerShell, Windows) hacen los mismos pasos, cada uno idempotente:

1. Verifican Python ≥ la versión mínima fijada en el script y crean `TP-Integrador/.venv` si no existe. Todo lo que se instala queda dentro de ese venv.
2. Instalan `backend/requirements.txt` si cambió desde la última instalación (huella de los `requirements*.txt` guardada en `.venv/.mosaic-stamp`).
3. Detectan la GPU e instalan la biblioteca que corresponde: con placa NVIDIA (`nvidia-smi` responde), `requirements-cuda.txt`; si no hay NVIDIA o PyCUDA no compila (falta el CUDA Toolkit), `requirements-opencl.txt`. Una falla se informa como advertencia y la aplicación sigue con CPU. La decisión se guarda en la huella para no reintentar en cada arranque; `--reinstall` fuerza otro intento y `--cpu-only` lo saltea.
4. Si no hay `node` con la versión mínima en el `PATH`, instalan `nodeenv` en el venv y con él Node LTS dentro del mismo venv. Después corren `npm ci` en `frontend/` si falta `node_modules` o cambió `package-lock.json`.
5. Crean `backend/.env` y `frontend/.env` a partir de `env.example` si no existen.
6. Levantan el backend (`python -m app.main` desde `backend/`), esperan a que `/api/state` responda, levantan el frontend (`npm run dev`) e imprimen la URL. Ctrl+C detiene ambos (`trap` en bash, `try/finally` en PowerShell) sin dejar procesos huérfanos.

La elección de CUDA u OpenCL en tiempo de ejecución la sigue haciendo el registro (D4): el script solo decide qué instalar.

### D12. Lenguaje visual: design system de `frontend/DESIGN.md`

La interfaz sigue el design system de `DESIGN.md` (hoy en la raíz del repo como `design.md`; se mueve a `TP-Integrador/frontend/DESIGN.md` para que viaje con el frontend). Ese documento describe un sitio de catálogo; acá se adapta a una herramienta de un solo flujo:

- **Tokens**: `styles/tokens.css` define como variables CSS todos los colores, tipografías, espaciados y radios de `DESIGN.md` (`--color-primary: #0066cc`, `--radius-pill`, `--space-section`...). Los componentes solo usan variables; un lint de estilos (`stylelint` con `color-no-hex` fuera de `tokens.css`) lo controla.
- **Tipografía**: `system-ui, -apple-system, BlinkMacSystemFont` y, como sustituto fuera de Apple, Inter instalada con `@fontsource/inter` (sin Google Fonts, para funcionar sin internet), con los ajustes de tracking y line-height que indica `DESIGN.md`. Cuerpo a 17 px, títulos a peso 600 con letter-spacing negativo, sin peso 500.
- **Layout sin sidebar**: no se usan `global-nav` ni `sub-nav-frosted` como navegación. El stepper ocupa ese lugar: una franja fija arriba de 52 px con el estilo de `sub-nav-frosted` (parchment al 80 % con `backdrop-filter: blur`), con los tres pasos en `{typography.button-utility}`; el actual en `{colors.ink}` peso 600, los completos como `text-link` (se puede volver a ellos) y los futuros en `{colors.ink-muted-48}`. Por debajo de 640 px se compacta a "Paso N de 3 · Nombre".
- **Contenido de cada paso**: un `product-tile-light` (o `product-tile-parchment`, alternando entre pasos) centrado, con ancho máximo de 980 px: título en `{typography.display-lg}`, una línea de bajada en `{typography.lead}` y la acción principal ("Siguiente", "Generar mosaico") como `button-primary`; "Atrás" como `button-secondary-pill`.
- **Controles**:
  - zonas de carga de imágenes: `store-utility-card` (blanco, hairline, `{rounded.lg}`), con las miniaturas en `{rounded.sm}`;
  - campos numéricos: con la forma de `search-input` (píldora, 44 px de alto);
  - resolución de tesela: tres `configurator-option-chip` (16, 32, 64 px), con el estado seleccionado en borde 2 px `{colors.primary-focus}`;
  - opacidad: slider con el riel en `{colors.hairline}` y el tramo activo en `{colors.primary}`;
  - formas de ejecución (paso 3): `store-utility-card` seleccionables con el mismo borde de selección; deshabilitadas con texto `{colors.ink-muted-48}` y el motivo en `{typography.caption}`.
- **Ejecución**: las barras de progreso usan `{colors.primary}` sobre `{colors.hairline}`, en un tile parchment.
- **Resultado**: el mosaico es "el producto". Se muestra en un `product-tile-dark` de borde a borde, centrado y con la única sombra del sistema (`rgba(0, 0, 0, 0.22) 3px 5px 30px`). Debajo van "Descargar" (`button-primary`), "Ver estadísticas" y "Volver a empezar" (`button-secondary-pill`). Las estadísticas se despliegan en un tile parchment debajo del resultado, con tablas en `{typography.caption}` y números con `font-variant-numeric: tabular-nums`.
- **Brechas de `DESIGN.md` que se completan**: el documento no define estados de error ni validación. Se agrega un único token `--color-error` (#d70015) solo para mensajes de validación y fallas, en `{typography.caption}` debajo del campo, sin cambiar el color de acento. Tampoco define tooltips: se usan fondo `{colors.ink}`, texto blanco en `{typography.caption}`, `{rounded.sm}` y sin sombra.
- **Interacción**: todo botón usa `transform: scale(0.95)` como estado presionado y `outline: 2px solid {colors.primary-focus}` como foco. Objetivos táctiles de al menos 44 × 44 px.

### D13. Patrones de este cambio

Productor/Consumidor (colas web↔worker), Command (mensajes `RunJob`/`Shutdown`), Observer (`ProgressHub` y la suscripción del frontend al WebSocket), Facade (`WorkerClient` y `api/client.ts`), State (reducer del stepper con transiciones explícitas). Se documentan en el README junto a los del cambio 1.

## Risks / Trade-offs

- [Codificar el PNG de un mosaico enorme tarda segundos] → Ocurre fuera de la medición y se muestra como "guardando resultado"; compresión PNG baja.
- [El hilo lector de `event_q` bloquea el apagado] → Se le envía un mensaje centinela y se usa `get(timeout=...)`.
- [Muchos mensajes de progreso saturan el WebSocket] → *Throttling* en el worker y solo cambios de fracción significativos.
- [Ctrl+C llega también al worker (mismo grupo de procesos)] → El worker ignora `SIGINT` y solo termina con `Shutdown` o por el `terminate()` del timeout.
- [Sin cancelación, un trabajo de CPU muy largo obliga a esperar] → La estimación con confirmación previa lo mitiga; reiniciar la app es la salida de emergencia.
- [El frontend agrega Node como dependencia fuera de Python] → Si el sistema no lo tiene, el script lo instala dentro del venv con `nodeenv`; la primera instalación necesita internet.
- [PyCUDA necesita el CUDA Toolkit para compilarse y la instalación puede fallar] → El script cae a OpenCL sobre la misma placa NVIDIA y lo informa; el README explica cómo instalar el Toolkit y reintentar con `--reinstall`.
- [Dos orígenes (Vite y backend) obligan a configurar CORS] → Un solo origen permitido, configurable y con valor por defecto coherente con el frontend.

## Open Questions

- Valores por defecto concretos de los límites (MB de subida, píxeles de salida, umbral de confirmación) y versiones mínimas de Python y Node: se ajustan al probar en las máquinas del grupo, sin cambiar las specs.
