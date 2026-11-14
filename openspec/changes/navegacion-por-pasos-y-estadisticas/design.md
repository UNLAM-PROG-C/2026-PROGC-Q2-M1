# Design

## Context

El stepper es un reducer puro (`wizard/wizardReducer.ts`, patrón State) con las fases `images → params → execution → running → result`. Solo las tres primeras (`CONFIG_STEPS`) son pasos navegables: `NEXT` y `BACK` se mueven dentro de esa lista y `GO_TO` solo acepta pasos anteriores. Desde `running` y `result` el stepper marca todo como completo y no ofrece links.

`ResultView` muestra el mosaico en un `product-tile` y, con "Ver estadísticas", agrega `StatsPanel` debajo. El visor (`MosaicViewer`) mide `--viewer-height: 70vh` y escucha la rueda con `passive: false` para hacer zoom, así que con el cursor sobre el mosaico la página no scrollea (ver proposal.md - Why).

## Goals / Non-Goals

**Goals:**
- Que la máquina de estados del stepper siga siendo la única fuente de las transiciones, ahora con cinco pasos y navegación hacia adelante.
- Que la pantalla de resultado entre en la ventana sin depender de su contenido (uno o dos mosaicos, con o sin fallas).

**Non-Goals:**
- Cambiar el zoom del visor (por ejemplo, exigir Ctrl + rueda): deja de ser necesario cuando la pantalla no scrollea.
- Navegar durante `running`: el trabajo es de la pestaña y al terminar la lleva sola al resultado.
- Cambiar el contenido de las estadísticas (tablas, gráfico, banda de verificación).

## Decisions

### D1. Fase `stats` y lista de cinco pasos
Se agrega la fase `stats` y `CONFIG_STEPS` se reemplaza por `WIZARD_STEPS = [images, params, execution, result, stats]`. `running` no es un paso: `stepIndex(running)` devuelve la posición de `result`, así el stepper muestra "4. Generando" como actual y la versión compacta "Paso 4 de 5 · Generando".

*Alternativa descartada:* dejar las estadísticas como estado local de `ResultView` (un toggle que reemplaza el mosaico). No aparecería en el stepper ni respondería a "Atrás"/"Siguiente" como los demás pasos.

### D2. Alcance de cada paso en el reducer
Una función `canReach(state, phase)` decide si un paso es alcanzable:

| Paso | Alcanzable si |
|---|---|
| images | siempre |
| params | no hay bloqueo de imágenes |
| execution | no hay bloqueo de imágenes ni de parámetros |
| result | hay `jobId` (un trabajo de esta pestaña) |
| stats | `resultReady` (ese trabajo terminó bien) |

`NEXT` avanza al siguiente si es alcanzable; `BACK` retrocede al anterior; `GO_TO` acepta cualquier paso alcanzable distinto del actual. Durante `running` las tres acciones no hacen nada. El nuevo campo `resultReady` se pone en `true` con `JOB_FINISHED` y al hidratar con un trabajo terminado, y en `false` con `JOB_STARTED`, `JOB_FAILED` y `RESTART`. Hace falta en el reducer (y no solo en la vista) porque el stepper decide con él si "5. Estadísticas" es un link.

`RESTART` mantiene su semántica (vuelve a `images` y descarta `jobId`): es "empezar de nuevo", no "ir al paso 1"; para eso está el stepper.

`JOB_STARTED` se acepta desde cualquier fase salvo `running` (antes, solo desde `execution`): mientras viaja `POST /api/jobs` se puede salir de la ejecución, ahora también hacia adelante con "Ver resultado", y el trabajo que lanzó la pestaña no debe quedar corriendo sin que nadie lo muestre.

*Alternativa descartada:* un índice "paso más lejano visitado". No sirve: si se cambian las imágenes o los parámetros, los pasos siguientes dejan de ser válidos aunque se hayan visitado, y el resultado sigue siendo válido aunque los parámetros hayan cambiado.

### D3. Resultado a alto de ventana
En la fase `result`, `<main>` recibe la clase `app-main--fit`: `height: calc(100dvh - var(--stepper-height))` y `display: flex; flex-direction: column`. El `product-tile` toma `flex: 1; min-height: 0` con padding vertical `--space-lg` en lugar de `--space-section`, y el escenario del visor `flex: 1; min-height: var(--viewer-min-height)` en lugar del alto fijo `--viewer-height`. En comparación, `.mosaic-pair` también es flex y cada figura reparte el alto. El mínimo del visor evita que en ventanas muy bajas el mosaico desaparezca: ahí la página vuelve a scrollear, que es preferible a un visor de 0 px. Por eso el `product-tile` conserva `min-height: auto` (y no `0`): no puede quedar más bajo que su contenido con el visor al mínimo, y el fondo oscuro sigue cubriendo las acciones cuando la página scrollea. La imagen del visor va con `position: absolute` para que su tamaño natural no empuje el alto del escenario; `.mosaic-pair` sigue siendo grid, con `grid-auto-rows: 1fr`.

*Alternativa descartada:* bajar `--viewer-height` a un `vh` menor. El alto del resto (título, fallas, acciones, banner de conexión) cambia según el trabajo y el ancho, así que ningún porcentaje fijo garantiza que entre.

### D4. Acciones de paso
`StepActions` suma una acción opcional `next` (`{label, onClick}`), que se muestra como píldora secundaria junto a la principal. La usan Ejecución ("Ver resultado", solo si el resultado es alcanzable) y queda disponible para los demás. En Resultado, "Ver estadísticas" es la acción principal (es el "Siguiente" de ese paso) y "Atrás" y "Volver a empezar" son secundarias; la descarga sigue en su lugar. En Estadísticas, "Atrás" y "Volver a empezar" van al final del contenido.

### D5. `StatsPanel` como paso
`StatsPanel` deja de ser un panel anexo y pasa a ser el contenido de la fase `stats` en `App.tsx`, con el mismo `StepTile` parchment y la misma lógica (tablas simples o `ComparisonStats`). Si el trabajo ya no está (otra pestaña lanzó uno nuevo) muestra el mismo mensaje que el resultado. La página scrollea normalmente porque `<main>` no tiene `app-main--fit` en esta fase.

## Risks / Trade-offs

- [El resultado ya no puede scrollear para ver algo que no entra] → Todo lo que no es el mosaico está en una sola fila de acciones; el mínimo del visor reactiva el scroll solo en ventanas muy bajas.
- [`100dvh` en navegadores viejos] → Se declara antes `100vh` como respaldo.
- [Pasos 4 y 5 alcanzables con parámetros que ya no coinciden con el resultado] → Es intencional: el resultado describe el trabajo que se ejecutó (su lead muestra backend y tamaño) y no el borrador actual.
