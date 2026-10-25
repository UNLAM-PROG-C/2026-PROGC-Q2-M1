# Navegación por pasos y estadísticas como paso 5

**En una frase:** el stepper pasa a tener cinco pasos (Imágenes, Parámetros, Ejecución, Resultado, Estadísticas) navegables para adelante y para atrás según lo que esté disponible, y la pantalla de resultado ocupa justo el alto de la ventana para que la rueda del mouse quede para el zoom.

## Flujo

1. **Navegador, hilo de UI:** el reducer agrega la fase `stats` y la lista `WIZARD_STEPS`. `running` no es un paso y ocupa la posición de `result` ([wizardReducer.ts:11-14](TP-Integrador/frontend/src/wizard/wizardReducer.ts#L11), [wizardReducer.ts:94-97](TP-Integrador/frontend/src/wizard/wizardReducer.ts#L94)).
2. **Hilo de UI:** `canReach` decide si cada paso se puede abrir: `result` necesita un `jobId` de esta pestaña y `stats` necesita `resultReady` ([wizardReducer.ts:100-117](TP-Integrador/frontend/src/wizard/wizardReducer.ts#L100)). El `Stepper` muestra como link todo paso alcanzable, menos durante `running` ([Stepper.tsx:40-43](TP-Integrador/frontend/src/wizard/Stepper.tsx#L40)).
3. **Hilo de UI:** `NEXT`, `BACK` y `GO_TO` pasan por `goTo`/`back`, que no hacen nada si la fase es `running` ([wizardReducer.ts:120-137](TP-Integrador/frontend/src/wizard/wizardReducer.ts#L120)). En Ejecución aparece "Ver resultado" si ya hay un resultado alcanzable ([ExecutionStep.tsx:88-91](TP-Integrador/frontend/src/steps/ExecutionStep.tsx#L88)).
4. **Evento asíncrono (WebSocket → hook):** cuando el snapshot del servidor marca el trabajo como `finished`/`failed`, `useWizard` despacha `JOB_FINISHED`/`JOB_FAILED` ([useWizard.ts:30-36](TP-Integrador/frontend/src/wizard/useWizard.ts#L30)). `jobEnded` lleva a `result` y fija `resultReady` ([wizardReducer.ts:169-172](TP-Integrador/frontend/src/wizard/wizardReducer.ts#L169)).
5. **Hilo de UI:** en `result`, `<main>` recibe `app-main--fit` y mide lo que queda debajo del stepper ([App.tsx:65](TP-Integrador/frontend/src/App.tsx#L65), [layout.css:70](TP-Integrador/frontend/src/styles/layout.css#L70)). "Ver estadísticas" despacha `NEXT` ([ResultView.tsx:105](TP-Integrador/frontend/src/result/ResultView.tsx#L105)) y `StatsPanel` se renderiza como paso propio ([App.tsx:48-49](TP-Integrador/frontend/src/App.tsx#L48)).

## Concurrencia y paralelismo

El cambio es solo de frontend: **no agrega procesos, hilos, kernels ni mensajes** nuevos en el backend, la API ni el WebSocket. Todo corre en el único hilo de JavaScript del navegador. Lo interesante es cómo una máquina de estados síncrona convive con eventos que llegan **de forma asíncrona** desde el worker, vía WebSocket, en cualquier momento. Es concurrencia por intercalado en el event loop del navegador, sin paralelismo.

| Unidad de ejecución | Cantidad | Qué hace | Dónde |
|---|---|---|---|
| Event loop del navegador (hilo de UI) | 1 por pestaña | Corre los clicks, el reducer y los renders | [wizardReducer.ts:185](TP-Integrador/frontend/src/wizard/wizardReducer.ts#L185) |
| Callbacks del WebSocket | 1 por mensaje | Actualizan el snapshot del servidor, que dispara el efecto de fin de trabajo | [useServerState.ts:24-26](TP-Integrador/frontend/src/app/useServerState.ts#L24) |

## Sincronización y comunicación

- **Reducer como única fuente de transiciones (patrón State):** clicks y eventos del servidor entran como acciones a un reducer puro. React las aplica de a una, así que no hay estados intermedios mezclados ([wizardReducer.ts:185-219](TP-Integrador/frontend/src/wizard/wizardReducer.ts#L185)).
- **`resultReady` en el reducer, no en la vista:** el stepper lo necesita para decidir si "5. Estadísticas" es un link. Se pone en `true` con `JOB_FINISHED` o al hidratar con un trabajo terminado, y en `false` con `JOB_STARTED`, `JOB_FAILED` y `RESTART` ([wizardReducer.ts:147](TP-Integrador/frontend/src/wizard/wizardReducer.ts#L147), [wizardReducer.ts:177](TP-Integrador/frontend/src/wizard/wizardReducer.ts#L177), [wizardReducer.ts:179](TP-Integrador/frontend/src/wizard/wizardReducer.ts#L179)).
- **Efecto idempotente:** el efecto que despacha `JOB_FINISHED` se vuelve a ejecutar en cada cambio de fase ([useWizard.ts:36](TP-Integrador/frontend/src/wizard/useWizard.ts#L36)). Si la pestaña va y viene entre Resultado, Estadísticas y Ejecución, la acción vuelve a llegar, pero `jobEnded` solo actúa en `running` y con el mismo `jobId`, así que no hace nada.
- **Trabajo de esta pestaña:** `ownJob` solo le pasa el trabajo a la vista si `job_id` coincide con el de la pestaña ([App.tsx:27-31](TP-Integrador/frontend/src/App.tsx#L27)).

## Riesgos y cómo se evitan

- **Navegar mientras el worker genera:** si se pudiera salir de `running`, el `JOB_FINISHED` llegaría con la pestaña en otra fase y `jobEnded` lo descartaría, así que el resultado nunca se mostraría solo. Por eso `goTo` y `back` bloquean `running` y el stepper no ofrece links en esa fase ([wizardReducer.ts:122](TP-Integrador/frontend/src/wizard/wizardReducer.ts#L122), [wizardReducer.ts:136](TP-Integrador/frontend/src/wizard/wizardReducer.ts#L136)).
- **Otra pestaña lanza un trabajo nuevo:** el backend guarda solo el último trabajo. `ownJob` devuelve `null` y tanto Resultado como Estadísticas muestran `UNAVAILABLE_REASON` ([ResultView.tsx:117-119](TP-Integrador/frontend/src/result/ResultView.tsx#L117), [StatsPanel.tsx:37-39](TP-Integrador/frontend/src/result/StatsPanel.tsx#L37)). `resultReady` queda en `true`, así que el link al paso 5 sigue activo, pero abre ese mensaje. Cuando ese trabajo ajeno termina, su `JOB_FINISHED` trae otro `jobId` y se ignora.
- **Carrera al lanzar un trabajo (resuelta):** mientras `POST /api/jobs` está en vuelo, solo se deshabilita "Generar mosaico" ([ExecutionStep.tsx:98](TP-Integrador/frontend/src/steps/ExecutionStep.tsx#L98)); "Ver resultado", "Atrás" y los links del stepper siguen activos. Si el usuario sale de `execution` antes de la respuesta, `JOB_STARTED` igual lleva la pestaña a `running` desde cualquier fase ([wizardReducer.ts:179](TP-Integrador/frontend/src/wizard/wizardReducer.ts#L179)): el trabajo lo lanzó esta pestaña y, si se ignorara, correría en el worker sin que nadie mostrara su progreso.

## Para recordar

- **Máquina de estados + eventos asíncronos:** las guardas (`phase === 'running'`, `jobId` igual) hacen que un evento tardío o repetido no rompa el estado.
- **Bloquear transiciones en la sección crítica de la UI:** durante `running` no se navega. Es más simple que reconciliar un resultado que llega cuando la pestaña está en otra fase.
- **Diferencia con el design:** D3 pide `min-height: 0` en el `product-tile`, pero el código lo omite a propósito para que el visor no baje de `--viewer-min-height` ([result.css:15-18](TP-Integrador/frontend/src/styles/result.css#L15)). Además, `.mosaic-pair` es grid, no flex.
