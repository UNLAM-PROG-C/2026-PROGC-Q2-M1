# Tasks

## 1. Verificación

- [ ] 1.1 Implementar `app/core/verification.py` (digest por celda, comparación de `topk_idx` y digests contra la referencia, `VerificationSummary`); verificar con tests: resultados idénticos → 0 celdas, una fila de `topk_idx` alterada → 1 celda, un píxel alterado en una celda → 1 celda, ambas en la misma celda → 1 celda.

## 2. Worker

- [ ] 2.1 Extender `JobRunner` para varios backends: orden CUDA → OpenCL → CPU, carga y `choice` únicos, digest y `topk_idx` por backend, liberación de la imagen tras guardarla, `BackendFailed` sin cortar la comparación, `ComparisonFinished` con referencia CPU o primer backend; verificar con tests con backends falsos: orden respetado, una sola carga, falla aislada y elección de referencia.
- [ ] 2.2 Validar en el proceso web el pedido de comparación (al menos dos backends, todos disponibles) y aplicar la estimación de CPU; verificar con tests de API: un backend → 400, backend no disponible → 400, comparación válida aceptada.

## 3. Interfaz

- [ ] 3.1 Guardar Chart.js 4 con versión fija y su licencia en `static/vendor/`; verificar que la página carga sin conexión a internet.
- [ ] 3.2 Agregar el modo "Comparar" a `form.js` (casillas por backend, mínimo dos, no disponibles deshabilitados) y el progreso por backend; verificar a mano los escenarios "Un solo backend marcado" y "Resultados parciales".
- [ ] 3.3 Implementar `compare.js`: gráfico agrupado con interruptor lineal/logarítmico (logarítmico por defecto si la razón supera 100), tabla de speedup con "—" ante datos faltantes, banda de verificación y mensaje "incluí CPU secuencial para ver el speedup"; verificar con un test de JS sin dependencias (o a mano con datos fijos) que 30.000/150 se muestra como "200×".
- [ ] 3.4 Implementar las imágenes lado a lado con zoom sincronizado reutilizando `preview.js`; verificar a mano que acercar una imagen mueve las demás.

## 4. Documentación e integración

- [ ] 4.1 Documentar en el README el modo comparación: cómo elegir backends, cómo leer el gráfico, el speedup (que el total incluye transferencias) y la verificación; verificar con una comparación real CPU + GPU y agregar una captura al README.
- [ ] 4.2 Prueba de punta a punta con los tres backends en una máquina NVIDIA (CUDA + OpenCL sobre la misma placa) y con CPU + OpenCL en macOS, comprobando que las celdas distintas, si las hay, quedan por debajo del umbral de los tests de equivalencia; registrar tiempos y capturas en el PR.

## Workflow follow-up

- Requiere archivados los cambios 1 a 3.
- PR contra `develop` con tres aprobaciones; archivar antes de aplicar `agregar-benchmark`.
