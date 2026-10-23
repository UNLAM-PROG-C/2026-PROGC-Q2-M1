# Tasks

## 1. Verificación

- [x] 1.1 Implementar `backend/app/core/verification.py` (digest por celda, comparación de `topk_idx` y digests contra la referencia, `VerificationSummary`); verificar con tests: resultados idénticos → 0 celdas, una fila de `topk_idx` alterada → 1 celda, un píxel alterado en una celda → 1 celda, ambas en la misma celda → 1 celda.

## 2. Backend

- [x] 2.1 Extender `JobRunner` para varios backends: orden de la lista recibida, carga y `choice` únicos, digest y `topk_idx` por backend, liberación de la imagen tras guardarla, `BackendFailed` sin cortar la ejecución, `ComparisonFinished` con referencia CPU; verificar con tests con backends falsos: orden respetado, una sola carga, falla de la GPU aislada y CPU como referencia.
- [x] 2.2 Agregar la forma `both` a la traducción del proceso web (`[GPU preferida, cpu]`) y aplicar la estimación de CPU; verificar con tests de API: `both` sin GPU → 400 con motivo, `both` con CUDA → `[cuda, cpu]`, `both` con solo OpenCL → `[opencl, cpu]`.

## 3. Frontend

- [x] 3.1 Agregar `chart.js` y `react-chartjs-2` con versión fija a `frontend/package.json`; verificar que `npm run build` pasa y que la página carga sin conexión a internet.
- [x] 3.2 Agregar la tarjeta "Ambas (CPU y GPU)" a `ExecutionStep` (deshabilitada sin GPU, estimación de CPU) y el progreso por backend a `ProgressView`; verificar con un test que sin GPU "Ambas" no es elegible y a mano el escenario "GPU terminada, CPU en curso".
- [x] 3.3 Implementar `result/speedup.ts` y `ComparisonStats.tsx` (banda de verificación, gráfico agrupado con interruptor lineal/logarítmico —logarítmico por defecto si la razón supera 100—, `TimingsTable` con columnas por backend y speedup, aviso "sin comparación" si falló la GPU, colores tomados de `tokens.css` según design D5); verificar con tests de Vitest que 30.000/150 se muestra como "200×" y que un tiempo faltante muestra "—".
- [x] 3.4 Mostrar los dos mosaicos lado a lado en `ResultView` con zoom sincronizado reutilizando `MosaicViewer` y una descarga por mosaico; verificar a mano que acercar uno mueve el otro y que cada descarga baja el archivo correcto.

## 4. Documentación e integración

- [x] 4.1 Documentar en el README la opción "Ambas": cuándo está disponible, cómo leer el gráfico, el speedup (que el total incluye transferencias) y la verificación; verificar con una comparación real CPU + GPU y agregar una captura al README.
- [ ] 4.2 Prueba de punta a punta con "Ambas" en una máquina NVIDIA (CPU + CUDA) y en macOS (CPU + OpenCL), comprobando que las celdas distintas, si las hay, quedan por debajo del umbral de los tests de equivalencia, y que "Volver a empezar" conserva las imágenes; registrar tiempos y capturas en el PR.

## Verificación (2026-10-23, Windows 11, RTX 2080 SUPER, Ryzen)

- Interfaz con "Ambas" (CPU + CUDA), 2.000 teselas, 400 × 300 celdas, `tile_px` 32: la tarjeta muestra la estimación de CPU (~18 s); durante la ejecución se vio la GPU completa y la barra de matching de la CPU avanzando (3.2). Resultado: los dos mosaicos lado a lado, "Acercar" en uno aplicó la misma transformación al otro y cada "Descargar" apunta a `/cuda/png` y `/cpu/png` (3.4). Estadísticas: "CUDA: 8 celdas difieren de CPU", eje logarítmico por defecto; matching 16.277,9 ms contra 91,7 ms (177×), total 17.579,5 ms contra 550,6 ms (32×) con la carga reutilizada. "Volver a empezar" conservó el lote y el objetivo. Captura en el README (4.1).
- OpenCL + CPU por el `JobRunner` real (mismo lote): Radeon integrada 8 celdas distintas (matching 2.080,9 ms), RTX con `OPENCL_DEVICE=NVIDIA` 6 celdas (118,1 ms). Las celdas distintas (≤ 0,007 %) quedan muy por debajo del 1 % que admiten los tests de equivalencia (`MIN_MATCHING_CELLS_RATIO`).
- **Pendiente de 4.2:** la prueba en macOS (CPU + OpenCL desde la interfaz) en la máquina de un compañero.

## Workflow follow-up

- Requiere archivados los cambios 1 a 3.
- PR contra `develop` con tres aprobaciones; archivar antes de aplicar `agregar-benchmark`.
