# Consistencia visual del stepper

**En una frase:** todas las pantallas del stepper (Imágenes, Parámetros, Ejecución, Generando, Resultado y Estadísticas) se arman con la misma plantilla, `StepTile`: encabezado arriba, contenido en el medio y una barra de acciones fija abajo, con una línea de mensajes reservada para que los botones nunca cambien de lugar.

## Flujo

1. **Hilo de UI:** `App` elige la fase y renderiza el paso que corresponde, igual que antes ([App.tsx:33-50](TP-Integrador/frontend/src/App.tsx#L33)).
2. **Hilo de UI:** cada paso arma su propio `StepActions` con el estado que tiene en ese momento y se lo pasa a `StepTile` por la ranura `actions`. `StepTile` siempre pone el título, la bajada, el contenido y el `footer.step-bar` en el mismo lugar ([StepTile.tsx:31-46](TP-Integrador/frontend/src/components/StepTile.tsx#L31)).
3. **Hilo de UI:** `StepActions` renderiza los botones y siempre la línea de mensajes, aunque esté vacía. Muestra `error ?? blocker ?? note`, y cualquier `blocker` deshabilita la acción principal ([StepActions.tsx:33-55](TP-Integrador/frontend/src/components/StepActions.tsx#L33)).
4. **CSS:** `.app-main` es una columna flex con el alto de la ventana y `.step-bar` usa `position: sticky; bottom: 0; margin-top: auto`. Con poco contenido la barra baja al fondo; con mucho, la página scrollea y la barra queda pegada abajo ([layout.css:66-71](TP-Integrador/frontend/src/styles/layout.css#L66), [layout.css:155-162](TP-Integrador/frontend/src/styles/layout.css#L155)).
5. **Hilo de UI:** el resultado ya no tiene su `product-tile`. Pasa a ser un `StepTile tone="dark" fit`, y la descarga va como `children` de `MosaicViewer`, en la fila de zoom ([ResultView.tsx:63-72](TP-Integrador/frontend/src/result/ResultView.tsx#L63), [MosaicViewer.tsx:108-113](TP-Integrador/frontend/src/result/MosaicViewer.tsx#L108)).

## Concurrencia y paralelismo

El cambio es **solo visual**. No agrega procesos, hilos, kernels, endpoints ni mensajes de WebSocket. Todo corre en el único hilo de JavaScript de la pestaña. Lo que sí importa es que la barra muestra **estado asíncrono**: subidas, `fetch` y eventos del servidor que terminan en cualquier momento, intercalados en el event loop. Hay concurrencia, pero no paralelismo.

| Unidad de ejecución | Cantidad | Qué hace | Dónde |
|---|---|---|---|
| Event loop del navegador (hilo de UI) | 1 por pestaña | Clicks, renders y callbacks de promesas | [StepActions.tsx:43](TP-Integrador/frontend/src/components/StepActions.tsx#L43) |
| Subidas con progreso (promesas) | hasta 2 a la vez (lote y objetivo) | Actualizan `progress`, que se convierte en "subiendo imágenes…" | [useUpload.ts:23-32](TP-Integrador/frontend/src/steps/useUpload.ts#L23) |
| `POST /api/jobs` en vuelo | 0 o 1 | `sending` y `error` alimentan la barra de Ejecución | [ExecutionStep.tsx:64-95](TP-Integrador/frontend/src/steps/ExecutionStep.tsx#L64) |
| Callbacks del WebSocket | 1 por evento | Actualizan el snapshot que leen Generando, Resultado y la guarda de Ejecución | [useServerState.ts:24-26](TP-Integrador/frontend/src/app/useServerState.ts#L24) |

## Sincronización y comunicación

- **El estado asíncrono sigue viviendo en cada paso.** La barra no se movió a `App` justamente por esto (design D1): el progreso de subida ([ImagesStep.tsx:25](TP-Integrador/frontend/src/steps/ImagesStep.tsx#L25)), `sending`/`error` del `POST` y `confirming` son estado local de cada paso. Cada paso los traduce a `blocker`/`error`/`note` en el render ([ExecutionStep.tsx:128-131](TP-Integrador/frontend/src/steps/ExecutionStep.tsx#L128)).
- **Un solo trabajo a la vez entre pestañas:** cuando otra pestaña lanza un trabajo, llega por WebSocket. `runBlocker` lo detecta con `isJobRunning` y devuelve "hay un trabajo en curso", que aparece en la línea de mensajes y deshabilita "Generar mosaico" ([execution.ts:35-38](TP-Integrador/frontend/src/steps/execution.ts#L35)).
- **La confirmación de un trabajo largo usa la misma barra:** solo se muestra si `confirming && blocker === null` ([ExecutionStep.tsx:138-140](TP-Integrador/frontend/src/steps/ExecutionStep.tsx#L138)). Si mientras tanto el servidor pasa a estar ocupado, la confirmación se cierra y se ve la barra normal con el motivo de bloqueo.
- **Progreso y resultado sin cambios de protocolo:** `ProgressView` sigue leyendo `job_progress` del snapshot. Solo cambió el contenedor, y la barra quedó como una nota fija ([ProgressView.tsx:58](TP-Integrador/frontend/src/run/ProgressView.tsx#L58)).
- **Zoom sincronizado (Observer), sin cambios:** los dos mosaicos comparten un `ZoomController` ([ResultView.tsx:76](TP-Integrador/frontend/src/result/ResultView.tsx#L76)) y cada visor se suscribe con `useSyncExternalStore` ([useZoomPan.ts:44](TP-Integrador/frontend/src/result/useZoomPan.ts#L44)). `DownloadMenu` es un hijo más de la fila de controles: tiene su propio `open` y no toca la vista compartida ([DownloadMenu.tsx:20](TP-Integrador/frontend/src/result/DownloadMenu.tsx#L20)).

## Riesgos y cómo se evitan

- **Doble envío del trabajo:** mientras el `POST` está en vuelo, `blocker = 'enviando el trabajo…'` deshabilita la principal, así no se puede lanzar dos veces ([ExecutionStep.tsx:131](TP-Integrador/frontend/src/steps/ExecutionStep.tsx#L131)).
- **Error viejo que tapa el bloqueo actual:** la prioridad de la línea es `error > blocker`. Si el `POST` falló (por ejemplo, porque otra pestaña ganó la carrera) y después llega por WebSocket el trabajo de la otra pestaña, ese rechazo ya no describe la situación. `useStartJob` lo descarta apenas aparece un bloqueo externo, así la línea muestra "hay un trabajo en curso" y el error no reaparece cuando ese trabajo termina ([ExecutionStep.tsx:69](TP-Integrador/frontend/src/steps/ExecutionStep.tsx#L69)).
- **Confirmación que reaparece:** si la confirmación de un trabajo largo queda tapada por el trabajo de otra pestaña, `useConfirmation` la cierra. Cuando ese trabajo termina, la barra vuelve a "Generar mosaico" y no a una confirmación que nadie pidió de nuevo ([ExecutionStep.tsx:112](TP-Integrador/frontend/src/steps/ExecutionStep.tsx#L112)).

## Para recordar

- **Template Method por composición:** `StepTile` fija el esqueleto y cada fase completa las ranuras. La vista no reconstruye la estructura, solo refleja el estado.
- **Estado asíncrono derivado en el render:** el mensaje de la barra no se guarda en ningún lado, se calcula en cada render a partir de `progress`, `sending`, `error` y el snapshot del servidor. Así no puede quedar desincronizado con el estado real. El único estado local que podría quedar viejo, el `error` del `POST` y la confirmación pendiente, se descarta cuando aparece un bloqueo externo.

## Marca del stepper

- **Qué cambió:** el componente `Brand` dibuja un isotipo de 4 teselas con `aria-hidden`, porque es decorativo y los lectores de pantalla no tienen que leerlo. Al lado va la palabra partida en "Foto" (light) y "mosaico" (semibold) ([Stepper.tsx:50-63](TP-Integrador/frontend/src/wizard/Stepper.tsx#L50)).
- **Por qué baja a 17px:** `.stepper__brand` pasa de `--type-tagline-size` (21px) a `--type-body-size` (17px) para quedar al nivel de los pasos en vez de competir con ellos ([layout.css:21-30](TP-Integrador/frontend/src/styles/layout.css#L21), [tokens.css:69-74](TP-Integrador/frontend/src/styles/tokens.css#L69)).
- **Sin números mágicos:** el tamaño, la separación, el radio y la opacidad de las teselas salen de los tokens `--brand-tile-*` ([tokens.css:132-136](TP-Integrador/frontend/src/styles/tokens.css#L132)). Los tonos son el acento con distinta opacidad más una tesela en ink, así que no se suman colores ([layout.css:42-59](TP-Integrador/frontend/src/styles/layout.css#L42)).
- **Concurrencia:** ninguna. Es markup estático y CSS, sin estado, efectos ni eventos asíncronos. No toca el event loop ni la comunicación con el servidor.
