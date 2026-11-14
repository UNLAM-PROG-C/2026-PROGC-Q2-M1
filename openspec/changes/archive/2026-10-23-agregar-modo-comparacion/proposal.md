# Proposal

## Why

Con la aplicación del cambio 3 se puede ejecutar un trabajo en CPU o en GPU, pero la comparación —el corazón didáctico del TP— queda a cargo de la persona, que tendría que anotar tiempos de varias corridas y confiar en que los resultados son iguales. Una forma de ejecución "Ambas" ejecuta el mismo trabajo en CPU y en GPU bajo condiciones idénticas, y la sección de estadísticas muestra juntos los tiempos, el speedup y la prueba de que el resultado es el mismo.

Es el **cambio 4 de 5**. Depende de los cambios 1 a 3; el protocolo del cambio 3 ya admite una lista de backends y la interfaz ya tiene el paso 3 y el botón "Ver estadísticas".

## What Changes

- Tercera opción en el paso 3 del stepper: **"Ambas (CPU y GPU)"**, habilitada solo si hay una GPU disponible. La GPU es la misma que elige el sistema para la opción GPU (CUDA con NVIDIA, OpenCL en otro caso).
- Ejecución en secuencia, GPU primero y CPU después, con la misma carga, los mismos parámetros y el mismo `choice`.
- Pantalla de resultado con los dos mosaicos lado a lado, zoom sincronizado y descarga de cada uno.
- "Ver estadísticas" en modo comparativo: gráfico de barras de tiempo por etapa (Chart.js, instalado con npm), con escala logarítmica opcional; tabla de tiempos con una columna por backend; speedup de la GPU respecto de la CPU, total y por etapa; y verificación de resultados ("Resultados idénticos ✓" o la cantidad de celdas que difieren).
- Si la GPU falla durante la comparación, la CPU se ejecuta igual y la falla se informa.

## Capabilities

### New Capabilities
- `modo-comparacion`: ejecución del mismo trabajo en CPU y GPU, presentación comparativa de tiempos y speedup, y verificación de igualdad de resultados.

### Modified Capabilities
<!-- Ninguna: el protocolo y la interfaz del cambio 3 se extienden sin cambiar sus requisitos. -->

## Impact

- `backend/app/worker/` (ejecución de varios backends y verificación), `backend/app/core/verification.py` (nuevo), `backend/app/web/` (forma de ejecución `both`) y `frontend/src/` (opción "Ambas", resultado lado a lado, estadísticas comparativas).
- Sin dependencias nuevas de Python. En `frontend/package.json`: `chart.js` y `react-chartjs-2`, con versión fija en `package-lock.json`.
- Comparar CUDA contra OpenCL sobre la misma placa queda fuera de la interfaz: se hace con `benchmark.py` (cambio 5).
- README: cómo usar "Ambas" y cómo leer el speedup.
