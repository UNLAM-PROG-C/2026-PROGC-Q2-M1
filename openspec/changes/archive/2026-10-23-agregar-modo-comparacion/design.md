# Design

## Context

- El protocolo del cambio 3 ya manda una lista de backends en `RunJob` y emite un `BackendFinished` por backend; `JobRunner` ya cachea la carga; el proceso web ya traduce formas de ejecución (`cpu`, `gpu`) a backends con la GPU preferida (cambio 3, design D4). Este cambio agrega la forma `both`, el bucle sobre varios backends, la verificación y la vista comparativa.
- Las imágenes de salida pueden pesar cientos de MB (ver diseño de `agregar-backends-gpu`, D5): no se pueden tener dos en memoria a la vez para compararlas.
- La interfaz no expone CUDA y OpenCL por separado: la comparación es siempre CPU contra la GPU que eligió el sistema.

## Goals / Non-Goals

**Goals:**
- Comparación justa (misma entrada, ejecución secuencial, sin otro trabajo compitiendo) y verificación por celdas, que tolera diferencias de punto flotante.
- Resultados progresivos: la GPU termina en segundos y la CPU puede tardar minutos.

**Non-Goals:**
- Comparar CUDA contra OpenCL desde la interfaz: lo hace `benchmark.py` (cambio 5).
- Repeticiones y estadísticas (media, desvío): eso le corresponde a `benchmark.py`.
- Mostrar dónde difieren las celdas sobre la imagen (se puede agregar después).

## Decisions

### D1. Forma `both` y orden de ejecución: GPU primero, CPU al final

El proceso web traduce `both → [GPU preferida, cpu]` y rechaza con 400 si no hay GPU. Así la persona ve resultados en segundos y el backend largo corre al final. Alternativa descartada: CPU primero, para tener la referencia en memoria desde el principio; obligaría a esperar minutos antes de ver nada y no ahorra memoria gracias a D2.

### D2. Verificación por huellas por celda

`app/core/verification.py` calcula, apenas termina cada backend:
- `topk_idx` completo (`M·k·4` bytes, a lo sumo unos MB), que se guarda en memoria;
- un **digest por celda** de la imagen: `blake2b(digest_size=8)` del bloque `tile_px×tile_px×3` de cada celda (`M·8` bytes).

La imagen ya se escribió a disco y se libera. Al final, una celda difiere si su fila de `topk_idx` o su digest no coinciden con los de la referencia, que es siempre CPU. Una colisión de 64 bits es despreciable frente al objetivo (detectar diferencias de punto flotante). Alternativa descartada: guardar las imágenes y releerlas para comparar, que agrega segundos de decodificación PNG y mucha memoria.

La comparación ocurre en el worker y a la web solo viaja `VerificationSummary(reference, {backend: celdas_distintas_topk, celdas_distintas_imagen, celdas_distintas_total})`. La función acepta cualquier cantidad de backends para que `benchmark.py` la reutilice.

### D3. Mensajes nuevos

Se agrega `ComparisonFinished(job_id, verification)` al protocolo; `JobFinished` sigue marcando el fin. Un `BackendFailed(backend, motivo)` permite seguir con la CPU si falla la GPU (hoy un error termina el trabajo con `JobFailed`). Es una extensión compatible: un trabajo de una sola forma sigue emitiendo lo mismo que en el cambio 3.

### D4. Cálculo de speedup en el cliente

Los tiempos ya llegan por backend; `result/speedup.ts` calcula `t_cpu / t_gpu` por etapa y para el total, y muestra "—" si algún tiempo falta o es cero. Hacerlo en el cliente evita otro mensaje y es una función pura fácil de testear.

### D5. Resultado y estadísticas comparativas

- Paso 3: `ExecutionStep` suma la tarjeta "Ambas (CPU y GPU)", deshabilitada con el mismo motivo que GPU cuando no hay GPU. La estimación de CPU se aplica igual.
- Progreso: `ProgressView` muestra una barra por etapa para cada backend, en el orden de ejecución.
- Resultado: `ResultView` muestra los dos mosaicos lado a lado reutilizando `MosaicViewer` con un controlador de zoom compartido (Observer: cada vista se suscribe a los cambios de zoom y desplazamiento), cada uno con su `DownloadMenu`.
- `StatsPanel` en modo comparativo (`result/ComparisonStats.tsx`):
  - banda de verificación arriba: "Resultados idénticos ✓" o las celdas distintas;
  - Chart.js 4 vía `react-chartjs-2` (versión fija en `package-lock.json`) con barras agrupadas: categorías = etapas, transferencias y total; series = CPU y GPU; un interruptor cambia el eje Y entre `linear` y `logarithmic`;
  - `TimingsTable` con una columna por backend y una columna de speedup.
- Estilo (design system de `frontend/DESIGN.md`, cambio 3 design D12):
  - los dos mosaicos comparten el mismo `product-tile-dark`, en dos columnas que pasan a una por debajo de 834 px, cada uno con la sombra de producto;
  - "Ambas" es otra `OptionCard` del paso 3, con el mismo estado de selección y de deshabilitado;
  - el gráfico toma los colores de `tokens.css`: GPU en `{colors.primary}` y CPU en `{colors.ink-muted-48}` (no se agrega un segundo color de acento), sin grilla decorativa, ejes y leyenda en `{typography.caption}`;
  - la banda de verificación es texto en `{typography.body-strong}` sobre el tile parchment de las estadísticas, sin cajas de color; las diferencias se marcan con `--color-error`.

## Risks / Trade-offs

- [Calcular `blake2b` para 40.000 celdas en Python] → Unas decenas de ms, fuera de la medición; si hiciera falta se agrupa en Numba.
- [El gráfico en escala lineal "esconde" las barras de GPU] → Por eso existe el interruptor logarítmico, y se activa por defecto si la razón entre la barra más alta y la más baja supera 100.
- [La interfaz ya no muestra CUDA contra OpenCL] → Es la decisión de producto (la persona elige CPU o GPU); el benchmark del cambio 5 sigue midiendo los tres backends por separado.
