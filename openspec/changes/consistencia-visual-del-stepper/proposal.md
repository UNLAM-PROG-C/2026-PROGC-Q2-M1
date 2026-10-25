# Proposal

## Why

Los pasos del stepper no se ven como partes de una misma pantalla. Cada paso alterna el fondo sin una regla clara: claro, parchment, claro, oscuro. El resultado usa un contenedor propio, así que su título queda a otra altura y su bajada a otro tamaño. Los botones aparecen debajo del contenido y cambian de altura de un paso a otro: en Ejecución, "Generar mosaico" queda más arriba que el "Siguiente" de Parámetros. Los mensajes de carga y de error también cambian de lugar según el paso. El mockup revisado ("Stepper consistente") muestra cómo queda la interfaz con una sola estructura para todos los pasos.

## What Changes

- **Una sola estructura para todos los pasos**, incluido el resultado:
  - un encabezado con el título igual al nombre del paso en el stepper ("Imágenes", "Parámetros", "Ejecución", "Generando", "Resultado", "Estadísticas") y una bajada con la instrucción o el estado;
  - debajo, el contenido;
  - abajo de todo, las acciones.
- **El resultado deja de usar su propio contenedor** y pasa a usar el contenedor de paso en tono oscuro. Su título "Tu mosaico" / "Tus mosaicos" pasa a ser "Resultado". El fallo deja de ser una pantalla clara con el título "No se pudo generar el mosaico": pasa a ser el mismo paso Resultado en tono oscuro, con el motivo.
- **Regla de fondo según qué pasa en el paso:**
  - claro, donde la persona completa algo (Imágenes, Parámetros, Ejecución);
  - parchment, donde el sistema informa (Generando, Estadísticas);
  - oscuro, solo en el resultado, salga bien o falle.

  Parámetros pasa de parchment a claro.
- **Mismo espacio superior en todos los pasos y bajada al tamaño tagline (21 px).** Así el título no cambia de altura al navegar.
- **Barra de acciones fija abajo de la pantalla**, del ancho del contenido:
  - los botones quedan siempre a la misma altura, en el orden [Atrás] [acción principal] [secundarias];
  - una línea reservada debajo de los botones muestra el motivo de bloqueo o el error del paso, así los botones no se mueven cuando el mensaje aparece o desaparece;
  - en Estadísticas, que scrollea, las acciones quedan siempre a la vista. **BREAKING** respecto de "Estadísticas con scroll", que pedía las acciones al final del contenido.
- **Un solo botón principal por pantalla.** En el resultado, "Descargar" pasa a ser secundario y se ubica junto a los controles de zoom de cada mosaico. La acción principal queda en "Ver estadísticas".
- **Mensajes en lugares fijos:**
  - los errores generales del paso (por ejemplo, el rechazo del trabajo o el límite de salida) se muestran en la línea de la barra de acciones;
  - los errores de cada campo siguen junto a su campo;
  - los estados de carga ("Conectando con el backend…", "Cargando el resultado…") se muestran en la bajada, sin reemplazar el título.
- **El gris apagado (`ink-muted-48`) pasa de #7a7a7a a #6e6e73** para llegar al contraste AA (4,5:1) en texto de 14 px sobre fondo claro.

## Capabilities

### New Capabilities
<!-- Ninguna. -->

### Modified Capabilities
- `interfaz-web`: se agregan la estructura común de los pasos, la regla de fondo, la barra de acciones fija y el lugar único de los mensajes. "Lenguaje visual según el design system" pasa a exigir un solo botón principal por pantalla. "Estadísticas con scroll" pasa a tener las acciones siempre visibles en la barra fija, en lugar de al final del contenido. "Errores visibles" pasa a mostrar el fallo dentro del paso Resultado.

## Impact

- **Solo frontend** (`TP-Integrador/frontend/src/`):
  - `components/StepTile.tsx` y `components/StepActions.tsx`;
  - `App.tsx` (la barra de acciones dentro de la estructura de pantalla);
  - `steps/*Step.tsx`, `run/ProgressView.tsx`, `result/ResultView.tsx`, `result/StatsPanel.tsx`, `result/MosaicViewer.tsx` y `result/DownloadMenu.tsx`;
  - los estilos `layout.css`, `result.css`, `controls.css` y `tokens.css`;
  - los tests que buscan los títulos o la ubicación de las acciones: `result.test.tsx`, `comparison.test.tsx`, `ComparisonResult.test.tsx`, `ExecutionStep.test.tsx` y `ParamsStep.test.tsx`.
- `TP-Integrador/frontend/DESIGN.md`: el valor de Ink Muted 48.
- Sin cambios en el backend, la API ni el WebSocket.
- Depende de `navegacion-por-pasos-y-estadisticas`, que agrega el paso 5 y el requisito "Estadísticas con scroll". Ese cambio se archiva antes que este.
