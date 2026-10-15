# Proposal

## Why

El modo comparación muestra un trabajo puntual. Para la conclusión del TP hace falta ver **cómo escala** cada backend con el tamaño del problema, con repeticiones y sin la interfaz de por medio, y mostrar el caso contraintuitivo: en problemas muy chicos la GPU puede no ganar por el costo fijo de transferencias y lanzamiento de kernels. Eso requiere un benchmark reproducible que genere tabla y gráfico.

Es el **cambio 5 de 5** y cierra la propuesta inicial (incluida la revisión final del README).

## What Changes

- Script `benchmark.py` en la raíz del proyecto: ejecuta los backends disponibles (o los elegidos) sobre una grilla de tamaños N × M (por defecto N ∈ {100, 1.000, 5.000} y M ∈ {1.000, 10.000, 40.000}) con datos sintéticos reproducibles.
- Repeticiones por medición, con mediana y mínimo; verificación de equivalencia en cada tamaño.
- Salidas: tabla en consola (Markdown), CSV con todas las mediciones y gráfico PNG de tiempo vs. M·N por backend (log-log), más una tabla de speedup y el punto a partir del cual la GPU supera a la CPU.
- Límite configurable para omitir las combinaciones en las que la CPU tardaría demasiado, informando la estimación.
- README final: instalación por plataforma revisada de punta a punta, uso del benchmark y lectura de resultados, con un resultado de ejemplo.

## Capabilities

### New Capabilities
- `benchmark`: medición reproducible de los backends sobre tamaños crecientes, sin interfaz, con tabla, CSV, gráfico, speedup y verificación.

### Modified Capabilities
<!-- Ninguna. -->

## Impact

- Nuevo `TP-Integrador/benchmark.py` y módulo de apoyo `app/bench/` (datos sintéticos y reporte). Usa directamente el registro de backends y la carga del cambio 1 y 2; no depende del worker ni de la web.
- Nueva dependencia: `matplotlib` en `requirements.txt`.
- `Makefile`: target `bench`. README: secciones finales.
