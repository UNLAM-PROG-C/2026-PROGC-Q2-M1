# Worker de cómputo e interfaz web

**En una frase:** el cómputo (pool de decodificación + backends CPU/GPU) se va a un proceso worker propio. Un proceso web FastAPI le manda órdenes y recibe eventos por dos colas, y le pasa el progreso al navegador por WebSocket. El frontend de Vite es otro proceso más, que no calcula nada.

## Flujo

1. **Proceso web, event loop:** en el *lifespan* arranca el `ProgressHub` y lanza el worker con `spawn` ([api.py:103-109](TP-Integrador/backend/app/web/api.py#L103), [worker_client.py:127-136](TP-Integrador/backend/app/web/worker_client.py#L127)).
2. **Worker, hilo principal:** detecta y precalienta los backends (crea los contextos de GPU), calibra la CPU, crea el pool de decodificación y publica `WorkerReady` ([worker/main.py:132-145](TP-Integrador/backend/app/worker/main.py#L132)).
3. **Web:** `POST /api/jobs` valida el pedido bajo un `asyncio.Lock`, traduce `cpu`/`gpu` a una lista de backends y encola `RunJob` en `command_q` ([jobs.py:149-162](TP-Integrador/backend/app/web/jobs.py#L149), [execution.py:30](TP-Integrador/backend/app/web/execution.py#L30)).
4. **Worker:** el hilo de órdenes acepta el trabajo y se lo pasa al hilo de trabajo, que carga las teselas (con el pool), corre cada backend y guarda PNG/JPEG/preview **fuera de la medición** ([job_runner.py:112-127](TP-Integrador/backend/app/worker/job_runner.py#L112), [job_runner.py:151-159](TP-Integrador/backend/app/worker/job_runner.py#L151)).
5. **Worker → web:** `JobProgress` (con *throttling* de 100 ms), `LoadFinished`, `BackendFinished` y `JobFinished`/`JobFailed` viajan por `event_q`. Solo van rutas y números, nunca arrays ([messages.py:1-12](TP-Integrador/backend/app/worker/messages.py#L1)).
6. **Web:** el hilo lector saca cada evento y lo pasa al event loop. Ahí `JobManager` actualiza el snapshot y el hub lo reenvía a todas las pestañas ([api.py:96-101](TP-Integrador/backend/app/web/api.py#L96)).

```
 navegador (N pestañas) ◀──WS── [Proceso web: event loop + threadpool + hilo lector + monitor]
        │ HTTP                          │ command_q (RunJob, Shutdown)   ▲ event_q (eventos)
        ▼                               ▼                                │
 [Vite / Node]                [Worker: hilo de órdenes ─queue─▶ hilo de trabajo] ──▶ [Pool spawn ×P]
```

## Concurrencia y paralelismo

| Unidad de ejecución | Cantidad | Qué hace | Dónde |
|---|---|---|---|
| Proceso web (uvicorn) | 1 (sin `--reload`, `workers=1`) | API, WebSocket y estado; no calcula | [main.py:31](TP-Integrador/backend/app/main.py#L31) |
| Tareas async (rutas, `_pump` del hub) | 1 por request/WS + 1 | Atender HTTP/WS y escribir en los sockets | [hub.py:33](TP-Integrador/backend/app/web/hub.py#L33) |
| Threadpool de Starlette | varios | Guardar subidas y borrar archivos sin bloquear el loop; `stop()` del worker | [routes.py:109](TP-Integrador/backend/app/web/routes.py#L109), [api.py:114](TP-Integrador/backend/app/web/api.py#L114) |
| Hilo lector `worker-events` | 1 por generación del worker | Consume `event_q` | [worker_client.py:138](TP-Integrador/backend/app/web/worker_client.py#L138) |
| Hilo `worker-monitor` | 1 | Espera el `sentinel` del worker y lo relanza si muere | [worker_client.py:151](TP-Integrador/backend/app/web/worker_client.py#L151) |
| Proceso worker (`spawn`) | 1 | Dueño de los contextos CUDA/OpenCL | [worker_client.py:130](TP-Integrador/backend/app/web/worker_client.py#L130) |
| Hilo de trabajo (principal del worker) | 1 | Ejecuta los trabajos de a uno | [worker/main.py:114](TP-Integrador/backend/app/worker/main.py#L114) |
| Hilo de órdenes `worker-commands` | 1 | Lee `command_q` y rechaza un segundo `RunJob` | [worker/main.py:100](TP-Integrador/backend/app/worker/main.py#L100) |
| Pool de decodificación (`spawn`) | 1 por núcleo por defecto | Decodifica teselas en paralelo | [tile_loader.py:105](TP-Integrador/backend/app/loading/tile_loader.py#L105) |
| Vite (Node) | 1 | Sirve la interfaz | [start.ps1:550](TP-Integrador/start.ps1#L550) |

Entre procesos hay **paralelismo real**: web, worker y pool corren en núcleos distintos, así que un trabajo de minutos no congela la API. Dentro de cada proceso, los hilos son **concurrentes** y el GIL los intercala. Igual no molesta, porque casi siempre están bloqueados en `get()`/`wait()` o en código nativo (GPU, Numba). El event loop es concurrencia cooperativa en un solo hilo. Se usa `spawn` y no `fork` porque un contexto CUDA no sobrevive a un `fork`.

## Sincronización y comunicación

- **Dos `multiprocessing.Queue`** entre web y worker (Productor/Consumidor + Command): por `command_q` van `RunJob`/`Shutdown` y por `event_q` los eventos. Son dataclasses congeladas que viajan por pickle ([messages.py:28-42](TP-Integrador/backend/app/worker/messages.py#L28)).
- **`queue.Queue` interna + `threading.Event _busy`** en el worker: el hilo de órdenes produce y el de trabajo consume. Si llega un `RunJob` con `_busy` activo, responde `JobRejected` sin interrumpir el trabajo en curso ([worker/main.py:102-111](TP-Integrador/backend/app/worker/main.py#L102)). Así los contextos de GPU se usan siempre desde un único hilo.
- **Puente hilo → event loop:** el callback del `WorkerClient` corre en el hilo lector o en el monitor. `loop.call_soon_threadsafe` encola `on_worker_event` en el loop, y entonces `JobManager` y el hub se tocan desde un solo hilo, sin locks ([api.py:119-122](TP-Integrador/backend/app/web/api.py#L119)).
- **`asyncio.Lock` en `JobManager.start`:** hace falta porque hay un `await` (crear la carpeta en el threadpool) entre el chequeo "¿hay trabajo en curso?" y la asignación del snapshot. Sin el lock, dos `POST` podrían pasar el chequeo a la vez. El segundo recibe 409 ([jobs.py:151-161](TP-Integrador/backend/app/web/jobs.py#L151)).
- **`threading.Lock` en `WorkerClient`:** protege el cambio de `_current` (la generación del worker) contra un `send()` concurrente ([worker_client.py:103](TP-Integrador/backend/app/web/worker_client.py#L103), [worker_client.py:134](TP-Integrador/backend/app/web/worker_client.py#L134)). `UploadStore` usa otro lock porque sus métodos corren en varios hilos del threadpool ([uploads.py:171](TP-Integrador/backend/app/web/uploads.py#L171)).
- **`ProgressHub` (Observer):** una `asyncio.Queue` y una sola tarea `_pump` escriben en todos los WebSocket. La suscripción de una pestaña nueva entra en la misma cola que los eventos, así que recibe el snapshot y después solo los eventos posteriores, sin repetidos ni perdidos ([hub.py:47-65](TP-Integrador/backend/app/web/hub.py#L47)). El frontend se reconecta con espera exponencial y, al conectar, recibe un `state` completo ([socket.ts:85-92](TP-Integrador/frontend/src/api/socket.ts#L85)).
- **Monitor con `wait([sentinel])`:** si el worker muere sin `Shutdown`, publica `WorkerCrashed` (el trabajo queda fallido) y lo relanza con colas nuevas ([worker_client.py:151-163](TP-Integrador/backend/app/web/worker_client.py#L151)).

## Apagado ordenado y Ctrl+C

- Ctrl+C le llega a todo el grupo de procesos de la consola. El worker y cada proceso del pool **ignoran `SIGINT`/`SIGBREAK`** ([worker/main.py:56-60](TP-Integrador/backend/app/worker/main.py#L56), [worker/main.py:137](TP-Integrador/backend/app/worker/main.py#L137)). Solo uvicorn reacciona y corre el *lifespan* de apagado.
- `stop()` (en el threadpool, para que el loop siga entregando eventos): `Shutdown` → `join(timeout)` → `terminate()` si no alcanzó ([worker_client.py:109-125](TP-Integrador/backend/app/web/worker_client.py#L109)). Después `_retire` encola un centinela `_StopReading` para que el lector vacíe lo pendiente y termine, y cierra las colas con `cancel_join_thread()` para no colgarse en un *feeder* lleno ([worker_client.py:166-173](TP-Integrador/backend/app/web/worker_client.py#L166)). El `finally` del worker cierra el pool y libera los contextos de GPU ([worker/main.py:146-149](TP-Integrador/backend/app/worker/main.py#L146)).
- **`start.ps1`:** lanza backend y Vite con `-NoNewWindow`. Vite arranca con `node` directo para evitar el "¿Desea terminar el trabajo por lotes?" de `cmd.exe` ([start.ps1:548-555](TP-Integrador/start.ps1#L548)). Cada 5 s registra los PID de todos los descendientes junto con su **fecha de creación** ([start.ps1:467-495](TP-Integrador/start.ps1#L467)). Así, si muere un intermedio (el lanzador `python.exe` del venv), el worker sigue registrado, y un PID reutilizado por otro programa no se mata. En el `finally` espera 10 s a que terminen por su cuenta y fuerza con `Stop-Process` lo que quede ([start.ps1:506-526](TP-Integrador/start.ps1#L506)).
- **`start.sh`:** usa `set -m` para que cada hijo quede en su propio grupo. El Ctrl+C solo le llega al script, que con `trap` manda `INT` al grupo del backend y `TERM` al de Vite, espera y termina con `KILL` ([start.sh:417-435](TP-Integrador/start.sh#L417), [start.sh:452-458](TP-Integrador/start.sh#L452)).

## Riesgos y cómo se evitan

- **Dos trabajos a la vez sobre la GPU:** hay doble barrera: el lock + 409 en la web y `_busy` + `JobRejected` en el worker. Para que la barrera del worker no rechace de más, `execute()` *devuelve* el evento final en vez de publicarlo ([job_runner.py:112](TP-Integrador/backend/app/worker/job_runner.py#L112)). `_serve` primero llama a `job_done()` y recién después encola `JobFinished`/`JobFailed` ([worker/main.py:125-129](TP-Integrador/backend/app/worker/main.py#L125)). La web solo acepta otro trabajo cuando recibe ese evento, así que el `RunJob` siguiente siempre encuentra al worker libre.
- **Lecturas del snapshot a medias:** `GET /api/state` y la descarga de resultados son `async` ([routes.py:79-80](TP-Integrador/backend/app/web/routes.py#L79), [routes.py:164](TP-Integrador/backend/app/web/routes.py#L164)). Corren en el event loop, el mismo hilo que aplica los eventos del worker, y entre dos `await` nadie más toca `JobManager`. Por eso nunca ven `results` a mitad de un cambio. Las rutas `def` (que van al threadpool) solo leen el `UploadStore`.
- **Borrar el lote que va a leer el worker:** la reserva y el borrado comparten el `threading.Lock` del `UploadStore`. `create_job_dir` verifica que el lote y el objetivo existan y los anota en `_in_use` bajo ese lock ([uploads.py:332-345](TP-Integrador/backend/app/web/uploads.py#L332)). Cada subida poda con el `_in_use` que lee adentro del mismo lock ([uploads.py:225-227](TP-Integrador/backend/app/web/uploads.py#L225)). Entonces, o el borrado va primero y el trabajo recibe `UploadGoneError` → 404 ([jobs.py:164-169](TP-Integrador/backend/app/web/jobs.py#L164)), o la reserva va primero y el lote se conserva. `release()` libera la reserva cuando el trabajo termina, falla o no se pudo despachar ([jobs.py:159](TP-Integrador/backend/app/web/jobs.py#L159), [jobs.py:266-270](TP-Integrador/backend/app/web/jobs.py#L266)).
- **Relanzar durante el apagado:** `_lifecycle_lock` vuelve atómicos "chequear `_stopping` y relanzar" en el monitor ([worker_client.py:157-163](TP-Integrador/backend/app/web/worker_client.py#L157)) y "marcar `_stopping` y tomar `_current`" en `stop()` ([worker_client.py:111-113](TP-Integrador/backend/app/web/worker_client.py#L111)). Si el monitor relanza primero, `stop()` apaga al worker nuevo. Si `stop()` marca primero, el monitor sale sin relanzar. Nunca queda un worker que nadie detiene.

## Para recordar

- **Productor/Consumidor + Command entre procesos:** mensajes chicos y serializables, y los datos pesados por disco o memoria compartida.
- **Confinamiento a un hilo:** los contextos de GPU viven en el hilo de trabajo y el estado web en el event loop. `call_soon_threadsafe` es el único punto de cruce.
- **Ciclo de vida de procesos:** centinelas, `join` con timeout, `terminate` como último recurso e ignorar `SIGINT` en los hijos para que el apagado lo decida uno solo.
