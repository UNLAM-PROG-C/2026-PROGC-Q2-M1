# Modo comparación CPU contra GPU ("Ambas")

**En una frase:** con la opción "Ambas" el mismo trabajo corre primero en la GPU y después en la CPU, siempre dentro del único hilo de trabajo del worker. De cada resultado se guarda una huella liviana para verificar celda por celda contra la CPU, y la interfaz muestra los dos mosaicos con el zoom sincronizado, el speedup y la verificación.

## Flujo

1. **Proceso web, event loop:** `POST /api/jobs` con `mode=both` se traduce a `(GPU preferida, cpu)`. Si no hay GPU, devuelve 400 con el motivo y no cae a "solo CPU" ([execution.py:46-56](TP-Integrador/backend/app/web/execution.py#L46)). Sale un único `RunJob` por `command_q`, igual que en el cambio 3.
2. **Worker, hilo de trabajo:** carga las teselas una sola vez (con el pool) y genera `choice` una sola vez para todos los backends ([job_runner.py:131-137](TP-Integrador/backend/app/worker/job_runner.py#L131)).
3. **Worker, hilo de trabajo:** `_compare` recorre los backends **en orden y de a uno**: GPU (kernels en el dispositivo) y después CPU ([job_runner.py:165-181](TP-Integrador/backend/app/worker/job_runner.py#L165)). Cada uno mide, guarda la imagen, toma su huella y publica `BackendFinished` ([job_runner.py:191-198](TP-Integrador/backend/app/worker/job_runner.py#L191)).
4. **Worker:** con las huellas de las dos, compara contra la CPU y publica `ComparisonFinished`. Después `_serve` marca al worker libre y encola `JobFinished` ([job_runner.py:180-181](TP-Integrador/backend/app/worker/job_runner.py#L180), [worker/main.py:125-129](TP-Integrador/backend/app/worker/main.py#L125)).
5. **Proceso web, event loop:** `JobManager` aplica cada evento al snapshot y el hub lo retransmite por WebSocket ([jobs.py:277-278](TP-Integrador/backend/app/web/jobs.py#L277), [api.py:96-99](TP-Integrador/backend/app/web/api.py#L96)).
6. **Navegador:** a los pocos segundos ya muestra la GPU terminada mientras la barra de matching de la CPU sigue avanzando. Al final aparecen los dos mosaicos y las estadísticas.

```
 [Worker: hilo de trabajo]  carga ─▶ GPU ─▶ huella ─▶ CPU ─▶ huella ─▶ verify
        │ event_q: JobProgress, BackendFinished(gpu), ..., BackendFinished(cpu), ComparisonFinished, JobFinished
        ▼
 [Web: event loop] ─ snapshot ─▶ hub ──WS──▶ navegador (progreso por backend, 2 visores)
```

## Concurrencia y paralelismo

| Unidad de ejecución | Cantidad | Qué hace | Dónde |
|---|---|---|---|
| Hilo de trabajo del worker | 1 | Corre GPU y CPU en secuencia, calcula huellas y verifica | [job_runner.py:171-177](TP-Integrador/backend/app/worker/job_runner.py#L171) |
| Kernels GPU (CUDA/OpenCL) | los del cambio 3 | Paralelismo de datos del backend GPU, sin cambios | backends del cambio 3 |
| Backend CPU | el del cambio 3 | Su paralelismo interno, sin cambios | backends del cambio 3 |
| Event loop del proceso web | 1 | Aplica `BackendFailed`/`ComparisonFinished` y los retransmite | [jobs.py:289-297](TP-Integrador/backend/app/web/jobs.py#L289) |

Este cambio **no agrega hilos ni procesos**. Lo que hace es decidir qué *no* corre en paralelo: los dos backends nunca se ejecutan a la vez. Si corrieran juntos, la CPU estaría compartida entre el backend CPU y el hilo que alimenta a la GPU, y además competirían por memoria y por el bus PCIe. El speedup quedaría contaminado. En secuencia, cada uno tiene la máquina para él solo, con la misma carga y el mismo `choice`. La única diferencia es el backend. Corre primero la GPU para ver un resultado en segundos y dejar al final la CPU, que puede tardar minutos.

## Sincronización y comunicación

- **`event_q` (Productor/Consumidor + Command), mensajes nuevos:** `BackendFailed(job_id, backend, reason)` y `ComparisonFinished(job_id, verification)` ([messages.py:98-112](TP-Integrador/backend/app/worker/messages.py#L98)). Siguen siendo livianos: `VerificationSummary` solo lleva conteos de celdas por backend, nunca arrays ([verification.py:36-50](TP-Integrador/backend/app/core/verification.py#L36)). Las huellas no salen del worker.
- **Huella por backend:** una copia de `topk_idx` más un digest `blake2b` de 8 bytes por celda ([verification.py:76-78](TP-Integrador/backend/app/core/verification.py#L76)). La imagen se recorre de a una fila de celdas para no duplicar su memoria ([verification.py:64-73](TP-Integrador/backend/app/core/verification.py#L64)). Se calcula después de `backend.run`, o sea fuera de la medición.
- **Liberación antes del backend siguiente:** `result` es local de `_run_backend`. Al volver solo quedan la huella, las rutas y los tiempos, así que nunca hay dos imágenes de cientos de MB en memoria a la vez ([job_runner.py:183-198](TP-Integrador/backend/app/worker/job_runner.py#L183)).
- **Puente al event loop:** igual que en el cambio 3, el hilo lector entrega cada evento con `call_soon_threadsafe`. `_on_comparison_event` escribe `failures`/`verification` en el snapshot desde el loop, sin locks ([jobs.py:289-297](TP-Integrador/backend/app/web/jobs.py#L289)). Una pestaña que se conecta tarde recibe esos campos en el `state` ([jobs.py:107-108](TP-Integrador/backend/app/web/jobs.py#L107)).
- **Progreso por backend en el frontend:** no hay mensajes extra. `backendProgress` lo deriva del snapshot: los backends anteriores al actual o con resultado van completos, el actual toma la fracción de `progress` y los siguientes quedan en cero ([stages.ts:57-67](TP-Integrador/frontend/src/run/stages.ts#L57)).
- **`ZoomController` (Observer):** guarda la vista y avisa a sus suscriptores solo si cambió ([zoomController.ts:26-35](TP-Integrador/frontend/src/result/zoomController.ts#L26)). `PairTile` crea uno y se lo pasa a los dos visores ([ResultView.tsx:76](TP-Integrador/frontend/src/result/ResultView.tsx#L76)). Cada visor se suscribe con `useSyncExternalStore`, que da una lectura consistente entre renders ([useZoomPan.ts:80-81](TP-Integrador/frontend/src/result/useZoomPan.ts#L80)). Un visor suelto usa su propio controlador ([MosaicViewer.tsx:43-44](TP-Integrador/frontend/src/result/MosaicViewer.tsx#L43)).

## Riesgos y cómo se evitan

- **Una falla de la GPU tira todo el trabajo:** en `_compare` cada backend tiene su propio `try`. La falla se publica como `BackendFailed` y la CPU sigue. Solo si fallan todos se relanza el error y termina en `JobFailed`. Si falta la CPU (la referencia), no se publica `ComparisonFinished` ([job_runner.py:172-181](TP-Integrador/backend/app/worker/job_runner.py#L172)).
- **Diferencias "falsas" por punto flotante:** en casi-empates la GPU puede elegir otra tesela. La verificación cuenta celdas en vez de exigir igualdad de bytes ([verification.py:81-88](TP-Integrador/backend/app/core/verification.py#L81)).
- **La medición no queda aislada del todo:** el proceso web y el navegador siguen vivos durante la CPU. Como casi siempre están bloqueados esperando eventos, el ruido es chico.

## Resultados medidos (RTX 2080 SUPER, Ryzen, 2.000 teselas, 400 × 300 celdas)

- CUDA contra CPU: matching 91,7 ms contra 16.277,9 ms (**177×**). Total 550,6 ms contra 17.579,5 ms (**32×**), porque el total incluye transferencias y composición. 8 celdas distintas.
- OpenCL: Radeon integrada 8 celdas (matching 2.080,9 ms), RTX por OpenCL 6 celdas (118,1 ms). En todos los casos queda ≤ 0,007 %, lejos del 1 % que admiten los tests de equivalencia.

## Para recordar

- **Medir bien exige serializar:** para comparar dos implementaciones paralelas, se ejecutan en secuencia sobre la misma entrada para que no compitan por recursos.
- **Mensajes chicos entre procesos:** se comparan huellas en el worker y a la web solo viajan conteos (Productor/Consumidor).
- **Observer** en dos lugares: el hub de WebSocket en el backend y el `ZoomController` en el frontend.
