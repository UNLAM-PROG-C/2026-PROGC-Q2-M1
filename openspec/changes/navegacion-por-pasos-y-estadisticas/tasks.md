# Tasks

## 1. Máquina de estados del stepper

- [x] 1.1 En `wizard/wizardReducer.ts`: agregar la fase `stats`, `WIZARD_STEPS` de cinco pasos, `stepIndex(running)` en la posición de `result`, el campo `resultReady` y `canReach` (design D1 y D2); `NEXT`, `BACK` y `GO_TO` en ambos sentidos y sin efecto durante `running`. Verificar con tests del reducer: execution → result solo con `jobId`, result → stats solo con `resultReady`, `BACK` desde stats y result, `GO_TO` hacia adelante y bloqueado sin resultado, y que los tests existentes siguen en verde.
- [x] 1.2 En `wizard/Stepper.tsx`: cinco pasos, links hacia todo paso alcanzable (no solo los anteriores), "Generando" en la posición 4 y compacto "Paso N de 5 · Nombre". Verificar con `Stepper.test.tsx` actualizado (link hacia adelante con resultado, sin links durante `running`).

## 2. Pasos y acciones

- [x] 2.1 `components/StepActions.tsx`: acción secundaria opcional `next` (design D4); `ExecutionStep` ofrece "Ver resultado" cuando el resultado es alcanzable. Verificar con `ExecutionStep.test.tsx`: aparece con `jobId` y no sin él.
- [x] 2.2 `ResultView`: quitar el toggle de estadísticas; "Ver estadísticas" (principal, solo si el trabajo terminó bien), "Atrás" y "Volver a empezar". `App.tsx` renderiza `StatsPanel` en la fase `stats` con "Atrás" y "Volver a empezar". Verificar con `result.test.tsx` y `comparison.test.tsx` actualizados: el resultado no muestra tablas, "Ver estadísticas" despacha `NEXT`, y las estadísticas (simples y comparativas) se ven en el paso 5.

## 3. Layout

- [x] 3.1 `app-main--fit` en la fase `result` y estilos de `product-tile`, visor y `mosaic-pair` a alto de ventana con `--viewer-min-height` (design D3); estadísticas sin restricción de alto. Verificar en el navegador (1440 × 900 y 1280 × 720, uno y dos mosaicos) que el resultado no tiene scroll vertical y que las estadísticas de "Ambas" scrollean en una ventana de 700 px de alto; `npm run lint` y `npm run build` limpios.

## 4. Documentación y cierre

- [x] 4.1 Actualizar el README del TP (stepper de cinco pasos, pasos 4 y 5, navegación) y `docs/explicaciones/` con el agente `explicador-concurrencia`; verificar que el README ya no menciona "Paso N de 3" ni el panel de estadísticas debajo del mosaico.
- [x] 4.2 Ejecutar `npm test` completo en el frontend y verificar que no hay fallas.

## Workflow follow-up

- Archivar el cambio después de la revisión del PR.
