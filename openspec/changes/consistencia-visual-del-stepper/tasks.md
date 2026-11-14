# Tasks

## 1. Plantilla de pantalla y barra de acciones

- [x] 1.1 `components/StepTile.tsx`: ranuras `actions` y `fit`, y el `footer.step-bar` dentro del tile (design D1). Estilos en `layout.css`:
  - `.app-main` como columna flex con alto mínimo de ventana;
  - `.step-tile` con `flex: 1`;
  - `.step-bar` sticky abajo, con `margin-top: auto`, el fondo del tono y una hairline (design D2);
  - padding superior `--space-xxl` y bajada a 21 px regular (design D7).

  Verificar con un test de `StepTile` que el título, la bajada, el contenido y las acciones se renderizan en ese orden y que la barra existe aunque no haya acciones.
- [x] 1.2 `components/StepActions.tsx`: línea de mensajes siempre presente con `aria-live`, prioridad `error` > `blocker` > `note`, `backLabel` y `next` renombrado a `secondary` (design D3). Estilo de error en tono oscuro. Verificar con tests de `StepActions`:
  - el botón principal se deshabilita con `blocker`;
  - `error` usa `role="alert"` y le gana a `blocker`;
  - la línea existe vacía;
  - el orden de los botones es Atrás, principal, secundaria.
- [x] 1.3 `tokens.css`: `--color-ink-muted-48: #6e6e73`, y actualizar el valor en `DESIGN.md` (design D8). Verificar con `npm run lint` (stylelint) limpio.

## 2. Pasos de configuración

- [x] 2.1 `ImagesStep` y `ParamsStep` pasan sus acciones por la ranura `actions`. Parámetros pasa a tono claro, "Conectando con el backend…" queda en la bajada con el título "Parámetros" y `errors.output` pasa al `error` de `StepActions`. Verificar con `ParamsStep.test.tsx`: el error de salida aparece en la barra y el error de columnas sigue junto al campo.
- [x] 2.2 `ExecutionStep`:
  - acciones en la ranura;
  - `job.error` como `error`;
  - "Ver resultado" como `secondary`;
  - la confirmación de un trabajo largo dentro de la misma barra: "Cancelar" / "Generar igual" y la advertencia en `note`, conservando el `alertdialog` "Confirmar trabajo largo" (design D3).

  Verificar con `ExecutionStep.test.tsx` actualizado: confirmación, cancelación, error del `POST` en la barra y orden Atrás / Generar mosaico / Ver resultado.

## 3. Progreso, resultado y estadísticas

- [x] 3.1 `ProgressView`: título "Generando" (igual que el stepper) y la barra con la nota "Al terminar se abre el resultado.". Verificar con `ProgressView.test.tsx`: el título coincide y el fallo de un backend sigue dentro de su grupo.
- [x] 3.2 `MosaicViewer` acepta `children` al final de sus controles, y `DownloadMenu` pasa a ser una píldora secundaria con un menú flotante sobre el botón (design D6). Verificar con `result.test.tsx`: los links PNG/JPEG aparecen al abrir el menú y "Descargar" no es el botón principal.
- [x] 3.3 `ResultView` dentro de `StepTile tone="dark" fit` (design D5):
  - título "Resultado" con uno o dos mosaicos;
  - la bajada de la comparación ("GPU y CPU · W × H px") y el pie de cada mosaico;
  - el fallo parcial en el `error` de la barra;
  - `FailedResult` y "Cargando el resultado…" en tono oscuro, con el título "Resultado".

  Eliminar `product-tile*` y `result-actions` de `result.css` y mover a `.step-tile--dark` las reglas de píldora secundaria y `text-link`. Verificar con `result.test.tsx`, `comparison.test.tsx` y `ComparisonResult.test.tsx` actualizados: títulos, único principal "Ver estadísticas", el motivo de la GPU caída en la barra y el resultado no disponible.
- [x] 3.4 `StatsPanel`: acciones en la ranura y, sin trabajo disponible, su propio tile "Estadísticas" parchment con el motivo en `error` (design D4). Verificar con `comparison.test.tsx` y `result.test.tsx`: el título sigue siendo "Estadísticas" cuando el resultado ya no está.

## 4. Verificación integrada y documentación

- [x] 4.1 Verificar en el navegador:
  - en una ventana de 1440 × 900, los botones de los pasos 1, 2, 3 y 5 y del resultado quedan a la misma altura y el título a la misma distancia del stepper;
  - el resultado no scrollea, con uno y con dos mosaicos;
  - en una ventana de 700 px de alto, las estadísticas de "Ambas" scrollean con la barra visible;
  - a 400 px de ancho, la barra no genera scroll horizontal;
  - abrir el menú de descarga no cambia el alto del visor.

  `npm run lint`, `npm run build` y `npm test` limpios.
- [x] 4.2 Actualizar el README del TP (estructura de los pasos, barra de acciones y regla de fondo) y generar `docs/explicaciones/consistencia-visual-del-stepper.md` con el agente `explicador-concurrencia`. Verificar que el README ya no menciona "Tu mosaico" ni la descarga junto a la navegación.

## Workflow follow-up

- Archivar primero `navegacion-por-pasos-y-estadisticas` y después este cambio, cuando se haya revisado.
