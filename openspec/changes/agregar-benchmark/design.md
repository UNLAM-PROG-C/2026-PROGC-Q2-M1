# Design

## Context

- El registro de backends (`agregar-backends-gpu`), la verificación (`agregar-modo-comparacion`, `app/core/verification.py`) y la calibración de CPU (`agregar-worker-e-interfaz-web`, D8) ya existen. El benchmark los usa directamente, sin worker ni web.
- La etapa común de carga no se compara, así que el benchmark genera `tiles_src` y `target_src` sintéticos directamente en memoria, sin decodificar archivos.

## Goals / Non-Goals

**Goals:**
- Una corrida por defecto que termine en tiempo razonable en una notebook (con CPU acotada por el límite de estimación).
- Resultados reproducibles y fáciles de pegar en el informe del TP (Markdown, CSV, PNG).

**Non-Goals:**
- Medir la etapa común de carga o la interfaz.
- Elegir la GPU automáticamente: a diferencia de la interfaz, el benchmark mide CUDA y OpenCL por separado (en una placa NVIDIA, sobre el mismo dispositivo) para poder compararlos.
- Perfilar kernels individuales (para eso están Nsight / `rocprof`).

## Decisions

### D1. Interfaz de línea de comandos

`python benchmark.py [--backends cuda,opencl,cpu] [--n 100,1000,5000] [--m 1000,10000,40000] [--tile-px 32] [--k 5] [--alpha 1.0] [--repeats 3] [--seed 0] [--max-cpu-seconds 600] [--out-dir resultados]`, con `argparse`. Los valores por defecto viven en `app/bench/defaults.py` (sin números mágicos en el script). `make bench` lo ejecuta con los valores por defecto.

`tile_px` por defecto es 32 y no 64: con M = 40.000 la salida de 64 px ocupa ~490 MB por backend, lo que mide sobre todo la copia D→H y puede no entrar en GPUs chicas.

### D2. Datos sintéticos

`app/bench/synthetic.py`:
- Teselas: cada una es un degradado entre dos colores aleatorios con una textura de ruido de baja amplitud, generados con `np.random.default_rng(seed)`. Así hay variedad de descriptores y pocos empates exactos.
- Objetivo: campo suave (suma de gaussianas de colores aleatorios) de forma `[rows·8, cols·8, 3]`.
- `(rows, cols)` para un M dado: el par de divisores con `rows·cols = M` cuya razón `cols/rows` más se acerca a 4:3 (1.000 → 25 × 40, 10.000 → 80 × 125, 40.000 → 160 × 250); el reporte informa el par usado.

### D3. Bucle de medición

Para cada backend: `warmup()` una vez (se informa su tiempo); luego, para cada (N, M) en orden creciente de M·N, `repeats` ejecuciones de `run()` con el mismo `choice`. Antes de CPU se consulta la estimación calibrada y, si supera `--max-cpu-seconds`, se registra "omitido". Entre combinaciones se liberan los arrays para no acumular memoria. Las combinaciones se ejecutan de a una: nada compite con la medición.

La verificación por combinación usa los digests por celda y `topk_idx` de `app/core/verification.py` (la referencia es la primera repetición de CPU, o del primer backend si CPU fue omitida o excluida).

### D4. Reporte

`app/bench/report.py`:
- Tabla Markdown: filas (N, M, M·N), columnas por backend con mediana del total (y mínimo entre paréntesis), más speedup.
- CSV con una fila por repetición y todas las columnas de `StageTimings`.
- `matplotlib` con backend `Agg`: total vs. M·N log-log, una línea por backend, marcadores huecos para combinaciones omitidas (en la posición estimada).
- Punto de cruce: para cada backend GPU, el menor M·N medido en el que `total_gpu < total_cpu`, o "la GPU fue más rápida en todos los tamaños medidos".

### D5. Calibración reutilizada

La calibración de CPU del cambio 3 debe vivir en `app/backends/cpu/calibration.py` (no en `app/worker/`) para que el benchmark la reutilice sin importar el worker. Si al implementar el cambio 3 quedó en otro lugar, la primera tarea de este cambio la mueve.

## Risks / Trade-offs

- [La corrida por defecto con CPU incluida puede tardar decenas de minutos] → `--max-cpu-seconds` con valor por defecto conservador y el script imprime una estimación total antes de empezar.
- [Las GPUs varían su frecuencia (boost/térmica) entre repeticiones] → Se informa mediana y mínimo, no solo el promedio, y el README recomienda enchufar la notebook y cerrar otras aplicaciones.
- [Datos sintéticos no representan fotos reales] → El tiempo depende de N, M, `tile_px` y `k`, no del contenido de las imágenes (no hay ramas dependientes de los datos salvo inserciones del top-k), así que la medición es representativa.
