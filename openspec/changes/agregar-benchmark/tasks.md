# Tasks

## 1. Preparación

- [ ] 1.1 Confirmar que la calibración de CPU está en `app/backends/cpu/calibration.py` (moverla si quedó en `app/worker/`) y agregar `matplotlib` a `requirements.txt`; verificar que la suite de tests completa sigue en verde.

## 2. Datos y medición

- [ ] 2.1 Implementar `app/bench/defaults.py` y `app/bench/synthetic.py` (teselas con degradado + ruido, objetivo suave, elección de `(rows, cols)` cercana a 4:3); verificar con tests: misma semilla → arrays idénticos, `rows·cols = M` para 1.000, 10.000 y 40.000, y que con N = 100 hay al menos 90 descriptores distintos.
- [ ] 2.2 Implementar el bucle de medición de design D3 (warmup, orden por M·N, repeticiones, omisión de CPU por estimación, liberación entre combinaciones, verificación por combinación); verificar con un test con backends falsos que se respetan repeticiones, omisiones y referencia.

## 3. Reporte y CLI

- [ ] 3.1 Implementar `app/bench/report.py` (tabla Markdown con mediana y mínimo, CSV por repetición, gráfico log-log con omitidos marcados, speedup y punto de cruce); verificar con tests sobre mediciones fijas: speedup 30.000/150 = 200×, cruce detectado y caso "la GPU fue más rápida en todos los tamaños".
- [ ] 3.2 Implementar `benchmark.py` (argparse de design D1, estado de backends al inicio, estimación total previa, guardia `__main__`) y el target `make bench`; verificar con `python benchmark.py --n 100 --m 1000 --repeats 1 --out-dir /tmp/bench` que genera tabla, CSV y PNG.

## 4. Documentación y cierre

- [ ] 4.1 Ejecutar el benchmark por defecto en al menos una máquina con GPU y en la de desarrollo, y agregar al README la tabla y el gráfico obtenidos con el hardware usado, explicando por qué la GPU puede perder en los tamaños chicos; verificar que los números del README coinciden con el CSV generado.
- [ ] 4.2 Revisar el README completo de punta a punta (instalación NVIDIA, AMD, macOS y solo CPU; ejecución de la app; modo comparación; benchmark; patrones de diseño; decisiones numéricas) y corregir lo desactualizado; verificar siguiendo la instalación solo CPU en un venv limpio y la de GPU en la máquina disponible.
- [ ] 4.3 Ejecutar la suite completa (`make test`) en macOS (CPU + OpenCL) y en la máquina NVIDIA (CPU + CUDA + OpenCL); verificar que no hay fallas y registrar en el PR qué tests se saltearon en cada máquina y por qué.

## Workflow follow-up

- Requiere archivados los cambios 1 a 4.
- PR contra `develop` con tres aprobaciones y archivado final del cambio.
