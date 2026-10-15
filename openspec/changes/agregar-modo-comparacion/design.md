# Design

## Context

- El protocolo del cambio 3 ya manda una lista de backends en `RunJob` y emite un `BackendFinished` por backend; `JobRunner` ya cachea la carga. Este cambio agrega el bucle sobre varios backends, la verificación y la vista.
- Las imágenes de salida pueden pesar cientos de MB (ver diseño de `agregar-backends-gpu`, D5): no se pueden tener tres en memoria a la vez para compararlas.

## Goals / Non-Goals

**Goals:**
- Comparación justa (misma entrada, ejecución secuencial, sin otro trabajo compitiendo) y verificación por celdas, que tolera diferencias de punto flotante.
- Resultados progresivos: la GPU termina en segundos y la CPU puede tardar minutos.

**Non-Goals:**
- Repeticiones y estadísticas (media, desvío): eso le corresponde a `benchmark.py` (cambio 5).
- Mostrar dónde difieren las celdas sobre la imagen (se puede agregar después).

## Decisions

### D1. Orden de ejecución: GPU primero, CPU al final

Así la persona ve resultados en segundos y el backend largo corre al final. Alternativa descartada: CPU primero, para tener la referencia en memoria desde el principio; obligaría a esperar minutos antes de ver nada y no ahorra memoria gracias a D2.

### D2. Verificación por huellas por celda

`app/core/verification.py` calcula, apenas termina cada backend:
- `topk_idx` completo (`M·k·4` bytes, a lo sumo unos MB), que se guarda en memoria;
- un **digest por celda** de la imagen: `blake2b(digest_size=8)` del bloque `tile_px×tile_px×3` de cada celda (`M·8` bytes).

La imagen ya se escribió a disco y se libera. Al final, una celda difiere si su fila de `topk_idx` o su digest no coinciden con los de la referencia. Una colisión de 64 bits es despreciable frente al objetivo (detectar diferencias de punto flotante). Alternativa descartada: guardar las imágenes y releerlas para comparar, que agrega segundos de decodificación PNG y mucha memoria.

La comparación ocurre en el worker y a la web solo viaja `VerificationSummary(reference, {backend: celdas_distintas_topk, celdas_distintas_imagen, celdas_distintas_total})`.

### D3. Mensajes nuevos

Se agrega `ComparisonFinished(job_id, verification)` al protocolo; `JobFinished` sigue marcando el fin. Un `BackendFailed(backend, motivo)` permite seguir con los demás backends (hoy un error termina el trabajo con `JobFailed`). Es una extensión compatible: un trabajo de un solo backend sigue emitiendo lo mismo que en el cambio 3.

### D4. Cálculo de speedup en el cliente

Los tiempos ya llegan por backend; `compare.js` calcula `t_cpu / t_gpu` por etapa y para el total, y muestra "—" si algún tiempo falta o es cero. Hacerlo en el cliente evita otro mensaje y permite recalcular si se oculta un backend.

### D5. Vista de comparación

- Chart.js 4 (versión fija, `static/vendor/chart.umd.min.js` + licencia) con barras agrupadas: categorías = etapas, transferencias y total; series = backends; un interruptor cambia el eje Y entre `linear` y `logarithmic`.
- Tabla de speedup: filas = etapas + total, columnas = backends GPU.
- Imágenes lado a lado reutilizando `preview.js` del cambio 3 con un controlador de zoom compartido (Observer: cada vista se suscribe a los cambios de zoom y desplazamiento).
- Banda de verificación arriba: "Resultados idénticos ✓" o una línea por backend con las celdas distintas.

## Risks / Trade-offs

- [Calcular `blake2b` para 40.000 celdas en Python] → Unas decenas de ms, fuera de la medición; si hiciera falta se agrupa en Numba.
- [La GPU y la CPU se ejecutan una después de la otra y la GPU puede estar "tibia" (clocks altos) para el segundo backend GPU] → Todos los backends ya hicieron `warmup()`; el benchmark del cambio 5 hace repeticiones para lo que necesite rigor estadístico.
- [El gráfico en escala lineal "esconde" las barras de GPU] → Por eso existe el interruptor logarítmico, y se activa por defecto si la razón entre la barra más alta y la más baja supera 100.
