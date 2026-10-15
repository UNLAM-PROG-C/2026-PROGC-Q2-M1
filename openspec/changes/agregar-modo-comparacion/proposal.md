# Proposal

## Why

Con la aplicación del cambio 3 se puede ejecutar un trabajo con un backend, pero la comparación —el corazón didáctico del TP— queda a cargo de la persona, que tendría que anotar tiempos de varias corridas y confiar en que los resultados son iguales. Un modo "Comparar" ejecuta el mismo trabajo con varios backends bajo condiciones idénticas, y muestra en una sola pantalla los tiempos, el speedup y la prueba de que el resultado es el mismo.

Es el **cambio 4 de 5**. Depende de los cambios 1 a 3; el protocolo del cambio 3 ya admite una lista de backends.

## What Changes

- Modo "Comparar" en la interfaz: se marcan los backends a incluir (dos o más disponibles) y se ejecutan en secuencia con la misma carga, los mismos parámetros y el mismo `choice`.
- Gráfico de barras de tiempo por etapa y backend (Chart.js, guardado localmente), con escala logarítmica opcional.
- Tabla de speedup de cada backend GPU respecto de CPU secuencial, total y por etapa.
- Verificación de resultados: igualdad de `topk_idx` y de la imagen final contra la referencia, con "Resultados idénticos ✓" o la cantidad de celdas que difieren.
- Imágenes resultantes lado a lado con zoom sincronizado.
- Un backend que falla no interrumpe la comparación de los demás.

## Capabilities

### New Capabilities
- `modo-comparacion`: ejecución del mismo trabajo con varios backends, presentación de tiempos y speedup, y verificación de igualdad de resultados.

### Modified Capabilities
<!-- Ninguna: el protocolo y la interfaz del cambio 3 se extienden sin cambiar sus requisitos. -->

## Impact

- `app/worker/` (ejecución de varios backends y verificación), `app/core/verification.py` (nuevo), `app/web/` (validación del pedido de comparación) y `static/` (vista de comparación, `vendor/chart.umd.min.js`).
- Sin dependencias nuevas de Python. Chart.js se guarda en el repo, con su versión y licencia.
- README: cómo usar el modo comparación y cómo leer el speedup.
