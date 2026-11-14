# Proposal

## Why

En la pantalla de resultado las estadísticas aparecen debajo del mosaico y hay que scrollear para verlas, pero el visor ocupa el 70 % de la ventana y captura la rueda para el zoom: en la práctica la página no scrollea y las estadísticas quedan fuera de alcance. Además la navegación es despareja: desde el resultado no se puede volver a la ejecución y desde la ejecución no se puede ir al último resultado sin generar otro.

## What Changes

- Las estadísticas pasan a ser **un paso propio** del stepper, después del resultado: el stepper queda con cinco pasos (Imágenes, Parámetros, Ejecución, Resultado, Estadísticas) y la versión compacta dice "Paso N de 5 · Nombre". **BREAKING** respecto del requisito "Estadísticas a pedido": el botón "Ver estadísticas" ya no despliega un panel debajo del mosaico, sino que avanza al paso 5.
- La pantalla de resultado **entra en la ventana sin scroll**: el visor del mosaico toma el alto que sobra después del título y las acciones.
- El último paso (Estadísticas) **scrollea normalmente**, porque el gráfico y las tablas pueden superar el alto de la ventana.
- **Todos los pasos permiten ir al anterior y al siguiente** cuando existe: botones "Atrás" y "Siguiente" en cada paso y links en el stepper hacia cualquier paso alcanzable, hacia atrás o hacia adelante. Resultado → Atrás vuelve a Ejecución; Ejecución ofrece ir al último resultado de la pestaña sin volver a generarlo.
- "Volver a empezar" se ofrece en Resultado y en Estadísticas.

## Capabilities

### New Capabilities
<!-- Ninguna. -->

### Modified Capabilities
- `interfaz-web`: el stepper pasa de tres a cinco pasos con navegación hacia adelante y hacia atrás; las estadísticas dejan de ser un panel a pedido y pasan a ser el paso 5; la pantalla de resultado no scrollea y la de estadísticas sí.

## Impact

- Frontend solamente (`TP-Integrador/frontend/src/`): `wizard/wizardReducer.ts` (fase `stats`, alcance de cada paso, `NEXT`/`BACK`/`GO_TO`), `wizard/Stepper.tsx`, `components/StepActions.tsx`, `steps/ExecutionStep.tsx`, `result/ResultView.tsx`, `result/StatsPanel.tsx` (pasa a ser el paso), `App.tsx` y los estilos `layout.css`/`result.css`/`tokens.css`. Tests de reducer, stepper y resultado.
- Sin cambios en el backend, la API ni el WebSocket.
- `README.md` del TP: la descripción del stepper.
