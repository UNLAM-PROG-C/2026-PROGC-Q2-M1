# Design

## Context

Hoy cada fase arma su pantalla por su cuenta:

- **Imágenes, Parámetros, Ejecución, Generando y Estadísticas** usan `StepTile` (título, bajada y contenido) y, salvo Generando, ponen `StepActions` al final del contenido. Por eso los botones quedan a distinta altura según cuánto mide cada paso.
- **El resultado** usa su propio `product-tile` (`result/ResultView.tsx`, `result.css`), con otra tipografía en la bajada, padding vertical reducido y una fila de acciones armada a mano (`result-actions`) que mezcla la descarga con la navegación.
- **El resultado fallido** usa `StepTile` en tono claro.

En la fase `result`, `<main>` tiene `app-main--fit`: alto de ventana y el visor con `flex: 1` (design D3 de `navegacion-por-pasos-y-estadisticas`). En el resto de las fases, la página scrollea normalmente y el stepper es `position: sticky`.

Los errores generales se muestran como `field-error` en lugares distintos según el paso:

- en Parámetros, `errors.output` debajo del panel de información;
- en Ejecución, `job.error` debajo de las tarjetas;
- en el resultado, `product-tile__failure` arriba del mosaico.

La confirmación de un trabajo largo (`ConfirmLongRun`) reemplaza a `StepActions` por un panel con otra disposición.

Ver proposal.md - Why para la motivación y el mockup "Stepper consistente" para el resultado buscado.

## Goals / Non-Goals

**Goals:**
- Que la estructura de pantalla (encabezado, contenido y barra de acciones) viva en un solo componente, y que ninguna fase la reconstruya.
- Que la posición de los botones no dependa del contenido ni de los mensajes.

**Non-Goals:**
- Cambiar la máquina de estados del stepper, la navegación o qué acciones ofrece cada paso. Solo cambia dónde y cómo se muestran.
- Cambiar el contenido de los pasos: zonas de carga, controles, tarjetas, tablas, gráfico y visor.
- Renombrar el token `--color-ink-muted-48` aunque su valor cambie (ver Risks).

## Decisions

### D1. `StepTile` como plantilla de pantalla con ranuras
`StepTile` pasa a recibir `title`, `lead`, `tone`, `children` (el contenido), `actions` (lo que va en la barra) y `fit` (alto de ventana, solo para el resultado). Renderiza:

```
<section class="step-tile step-tile--{tone}">
  <div class="step-tile__inner">  título · bajada · contenido  </div>
  <footer class="step-bar"> <div class="step-bar__inner">{actions}</div> </footer>
</section>
```

Cada fase decide qué va en cada ranura, pero no dónde se ubica. Es una plantilla por composición, en la línea de Template Method: el esqueleto es fijo y las fases completan los huecos. Se documenta en el comentario del componente.

*Alternativa descartada:* poner la barra en `App.tsx`, fuera del tile. Cada paso tendría que exponer sus acciones hacia arriba (estado de confirmación, error del `POST`, bloqueo de subida), y hoy ese estado vive en el paso. La barra también tiene que tomar el tono del paso, que solo conoce el paso.

### D2. Barra fija con `position: sticky`
- `.app-main` pasa a ser una columna flex con `min-height: calc(100dvh - var(--stepper-height))`.
- `.step-tile` ocupa el alto restante (`flex: 1`) y también es columna flex.
- `.step-bar` lleva `position: sticky; bottom: 0; margin-top: auto`, el fondo del tono del paso y una hairline arriba.

Con poco contenido, `margin-top: auto` baja la barra al fondo de la ventana. Con contenido más alto que la ventana (Estadísticas, Parámetros en pantallas bajas), la página scrollea como hoy y la barra queda pegada abajo. En el resultado (`fit`), el tile mide el alto de la ventana, el visor toma el espacio libre y la barra queda al final sin scroll, así que "Resultado sin scroll" se sigue cumpliendo.

*Alternativa descartada:* `position: fixed`. Saca la barra del flujo, obliga a compensar con `padding-bottom` en cada paso y a recalcular el ancho, y tapa contenido si la compensación falla.

*Alternativa descartada:* hacer scrollear solo el contenido del tile (`overflow: auto` dentro de un alto fijo), como en el mockup. La página dejaría de scrollear como documento y aparecería una segunda barra de scroll dentro de la pantalla.

### D3. Altura constante de la barra y línea de mensajes
`.step-bar__inner` tiene un alto mínimo igual a una fila de botones (`--touch-target`) más una línea de caption. `StepActions` siempre renderiza la línea de mensajes (`aria-live="polite"`), aunque esté vacía, así los botones no se mueven cuando aparece o desaparece un mensaje. La línea muestra, en este orden de prioridad:

1. `error`: un error general del paso, con `role="alert"`.
2. `blocker`: el motivo por el que no se puede avanzar.
3. `note`: un texto neutro.

Cambios en la API de `StepActions`:
- Se suman `error`, `note` y `backLabel` (por defecto "Atrás").
- `next` se renombra a `secondary`, porque no siempre lleva al paso siguiente: en el resultado es "Volver a empezar".

Usos:
- **Parámetros:** `errors.output` pasa a `error`.
- **Ejecución:** `job.error` pasa a `error`.
- **Resultado comparado:** si un backend falló, su `failureText` va a `error`.
- **Confirmación de un trabajo largo:** deja de ser un panel aparte. La misma barra muestra "Cancelar" (`backLabel`) y "Generar igual" (principal), con la advertencia en `note`, y conserva `role="alertdialog"` con su nombre accesible.
- **Generando:** no tiene botones. La barra muestra la nota "Al terminar se abre el resultado." con la misma altura.

Los errores de campo (`ParamField`, `ImageZones`) y el fallo de un backend dentro de su grupo de barras en Generando no cambian: pertenecen a un elemento del contenido, no al paso.

En tono oscuro, la línea de error se muestra en blanco semibold, como el actual `product-tile__failure`. El rojo de error no llega a 4,5:1 sobre `surface-tile-1`.

### D4. Tono por tipo de paso
| Fase | Tono |
|---|---|
| images, params, execution | `light` |
| running, stats | `parchment` |
| result (exitoso, fallido o cargando) | `dark` |

`StatsPanel` sin trabajo disponible deja de reutilizar `FailedResult`, que ahora es un paso "Resultado" oscuro. Muestra su propio `StepTile` "Estadísticas" parchment, con el motivo en `error` y "Atrás" / "Volver a empezar", para que el título siga coincidiendo con el stepper.

### D5. Resultado dentro de `StepTile`
`ResultView` arma un `StepTile tone="dark" fit` con:
- **Un mosaico:** título "Resultado" y la bajada de hoy (backend, dispositivo y tamaño).
- **Dos mosaicos:** título "Resultado", bajada "GPU y CPU · W × H px" (en el orden en que se ven los mosaicos) y el pie de cada mosaico con su backend y dispositivo.
- **Contenido:** el visor o el par de visores.
- **Acciones:**
  - trabajo terminado: [Atrás] [Ver estadísticas] [Volver a empezar];
  - trabajo fallido o no disponible: [Atrás] [Volver a empezar] como principal.

Se eliminan `product-tile*` y `result-actions` de `result.css`. La sombra de producto sigue sobre el escenario del visor. Las reglas que hoy cuelgan de `.product-tile` (píldora secundaria y `text-link` en azul sobre oscuro) pasan a `.step-tile--dark`.

### D6. Descarga en la barra del visor
`MosaicViewer` acepta `children`, que se renderizan al final de su fila de controles. `ResultView` pone ahí `DownloadMenu` en cada mosaico, tanto con uno como con dos, y el botón pasa a ser una píldora secundaria. Las opciones PNG/JPEG se abren como un menú flotante (`position: absolute`, arriba del botón) para que abrirlo no cambie el alto del visor en la pantalla a alto de ventana.

### D7. Tipografía y espaciado del encabezado
- `.step-tile` usa `--space-xxl` (48 px) arriba en todas las fases, y `--space-xl` antes de la barra.
- Se elimina el padding reducido que el resultado tenía por `app-main--fit`.
- La bajada usa el tamaño de `tagline` (21 px / 1.19) con peso regular. El peso 600 de `tagline` es para rótulos, no para texto corrido.
- En tono oscuro, la bajada usa `--color-body-muted`.

### D8. Token de texto apagado
`--color-ink-muted-48` pasa a `#6e6e73`, con 5,0:1 sobre blanco y 4,6:1 sobre parchment. Se actualiza `DESIGN.md`. Afecta a todo lo que ya usa el token: motivos de bloqueo, ayudas, pasos inactivos del stepper, encabezados de tabla y la serie CPU del gráfico comparativo.

## Risks / Trade-offs

- **[La barra fija resta alto útil, unos 76 px]** → En el resultado el espacio ya estaba ocupado por la fila de acciones. En el resto de los pasos el contenido scrollea por detrás.
- **[En pasos cortos, como Ejecución, queda espacio vacío entre el contenido y la barra]** → Es el comportamiento buscado: la posición estable de los botones vale más que la cercanía al contenido. El mockup lo mostró así.
- **[`position: sticky` deja de funcionar si algún ancestro tiene `overflow` distinto de `visible`]** → Ni `body`, ni `#root`, ni `.app-main` lo tienen. Se verifica en el navegador con Estadísticas en una ventana baja.
- **[El nombre `ink-muted-48` ya no describe el valor]** → Renombrarlo toca todos los estilos sin cambiar el comportamiento. Queda para un cambio de limpieza si hace falta.
- **[Tests que buscan el panel de confirmación, "Tu mosaico" o un `role="alert"` en otro lugar]** → Se actualizan en las tareas de cada componente. Los nombres accesibles que importan (el `alertdialog` de confirmación y los textos de error) se conservan.

## Migration Plan

Solo frontend, sin datos ni API. Se despliega con el build del frontend. Para volver atrás alcanza con revertir el commit. Depende de que `navegacion-por-pasos-y-estadisticas` esté archivado antes de archivar este cambio, porque el delta modifica "Estadísticas con scroll", que ese cambio agrega.
