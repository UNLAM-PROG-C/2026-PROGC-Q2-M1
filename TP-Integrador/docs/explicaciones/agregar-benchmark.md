# Benchmark sin interfaz de los backends

**En una frase:** `benchmark.py` mide CUDA, OpenCL y CPU sobre una grilla de tamaños N × M con datos sintéticos y repeticiones, verifica que den lo mismo y deja una tabla, un CSV y un gráfico log-log con el punto de cruce.

## Flujo

Todo pasa en **un solo proceso** de Python, sin worker ni servidor web.

1. **Detección y warmup:** el registro se arma solo con las fábricas de los backends pedidos y llama a `factory()` + `warmup()` de a uno. Ahí se compilan los kernels y Numba, fuera de cualquier medición ([benchmark.py:196-197](TP-Integrador/backend/benchmark.py#L196), [registry.py:140-151](TP-Integrador/backend/app/backends/registry.py#L140)). CUDA y OpenCL son entradas distintas aunque estén sobre la misma placa, así que cada uno tiene su propio contexto y se mide por separado.
2. **Calibración de CPU:** corre un problema sintético chico en el backend CPU y saca un costo por par celda-tesela, que después sirve para estimar y omitir combinaciones demasiado largas ([benchmark.py:145-151](TP-Integrador/backend/benchmark.py#L145), [calibration.py:52-64](TP-Integrador/backend/app/backends/cpu/calibration.py#L52)).
3. **Por cada (N, M), en orden creciente de M·N:** genera teselas, objetivo y un único `choice` ([measure.py:115-122](TP-Integrador/backend/app/bench/measure.py#L115), [synthetic.py:62-69](TP-Integrador/backend/app/bench/synthetic.py#L62)).
4. **Backends de a uno, `repeats` veces cada uno:** un `for` secuencial sobre los backends y, adentro, otro sobre las repeticiones ([measure.py:157-158](TP-Integrador/backend/app/bench/measure.py#L157), [measure.py:183-188](TP-Integrador/backend/app/bench/measure.py#L183)). Si la estimación de CPU supera `--max-cpu-seconds`, esa combinación queda como "omitida" ([measure.py:167-170](TP-Integrador/backend/app/bench/measure.py#L167)).
5. **Huella y verificación:** de la primera repetición se guarda la huella y la imagen se descarta. Al terminar la combinación se compara contra CPU, o contra el primer backend si CPU no corrió ([measure.py:125-129](TP-Integrador/backend/app/bench/measure.py#L125), [measure.py:197-202](TP-Integrador/backend/app/bench/measure.py#L197)).
6. **Reporte:** mediana (mínimo), speedup, punto de cruce, CSV y PNG ([benchmark.py:206-209](TP-Integrador/backend/benchmark.py#L206)).

## Concurrencia y paralelismo

| Unidad de ejecución | Cantidad | Qué hace | Dónde |
|---|---|---|---|
| Hilo principal del proceso | 1 | Detecta, calibra, genera datos, lanza cada backend y arma el reporte | [benchmark.py:189-210](TP-Integrador/backend/benchmark.py#L189) |
| Kernels CUDA / OpenCL | los del cambio 2 (un hilo de GPU por elemento de salida) | Paralelismo de datos dentro de `backend.run()` | backends del cambio 2 |
| Backend CPU | 1 hilo (Numba sin `parallel`, sin SIMD) | Referencia secuencial | [stages.py:5-7](TP-Integrador/backend/app/backends/cpu/stages.py#L5) |

El cambio **no agrega hilos ni procesos**. El único paralelismo es el de la GPU *adentro* de cada ejecución. Entre ejecuciones todo es secuencial a propósito: nunca corren dos backends a la vez, ni nada al lado de la medición. Así ningún backend le roba CPU, memoria ni bus PCIe al que se está midiendo. A diferencia del modo comparación, ni siquiera hay un proceso web vivo al lado.

## Sincronización y comunicación

- **Medición con el reloj de cada dispositivo:** en CPU se usa `perf_counter` ([cpu/backend.py:45-47](TP-Integrador/backend/app/backends/cpu/backend.py#L45)). En CUDA se graban eventos en el stream y `elapsed_ms` espera al evento de fin (`end.synchronize()`) antes de llamar a `time_till` ([cuda/timing.py:45-51](TP-Integrador/backend/app/backends/cuda/timing.py#L45)). En OpenCL la cola tiene `PROFILING_ENABLE` y se leen `profile.start`/`profile.end` de cada comando ([opencl/timing.py:22-23](TP-Integrador/backend/app/backends/opencl/timing.py#L22)). Como el lanzamiento de kernels es asíncrono, sin esas esperas el `perf_counter` del host mediría solo el encolado.
- **Por qué la primera repetición en GPU es más lenta:** el staging de host se reutiliza solo si entra. Como las combinaciones crecen, en la primera repetición el buffer queda chico, se libera y se vuelve a reservar memoria page-locked (CUDA: [cuda/backend.py:143-155](TP-Integrador/backend/app/backends/cuda/backend.py#L143)) o un buffer `ALLOC_HOST_PTR` (OpenCL: [opencl/backend.py:158-167](TP-Integrador/backend/app/backends/opencl/backend.py#L158)). Esa reserva entra en el tiempo. Las siguientes repeticiones ya lo reutilizan, y la mediana de 3 descarta la primera.
- **Liberación de memoria:** `result` es local de `_run_once`. Apenas se toma la huella (`topk_idx` + digest por celda, [verification.py:76-78](TP-Integrador/backend/app/core/verification.py#L76)) la imagen sale de alcance, así que nunca hay dos imágenes finales en memoria. Las entradas de la combinación se liberan antes de generar las de la siguiente.

## Riesgos y cómo se evitan

- **Compilación contaminando la medición:** el warmup corre en el registro antes del bucle y su tiempo se informa aparte ([benchmark.py:137-142](TP-Integrador/backend/benchmark.py#L137)).
- **Ruido de frecuencia (boost, temperatura):** se reportan mediana y mínimo, no el promedio. El README muestra un caso real con 68 contra 131 ms en la misma combinación.
- **Dos contextos vivos sobre la misma placa:** CUDA y OpenCL quedan abiertos durante toda la corrida. Aunque no se ejecuten a la vez, el staging y los buffers de uno ocupan memoria del dispositivo mientras mide el otro. Eso puede achicar el presupuesto de memoria de CUDA, que se calcula desde `mem_get_info()` ([cuda/backend.py:138-141](TP-Integrador/backend/app/backends/cuda/backend.py#L138)). No afecta el tiempo, pero conviene tenerlo en cuenta con problemas grandes.

## Resultados (ver "Benchmark" en el [README](TP-Integrador/README.md))

- Con la grilla por defecto la GPU gana de **11×** (M·N = 10⁵) a **110×** (CUDA, 2·10⁸). El matching escala con M·N y en la GPU se reparte entre miles de hilos.
- En problemas diminutos el **costo fijo** domina: transferencias H→D/D→H, staging, siete lanzamientos de kernel y las sincronizaciones. Con N = 10 y M = 12, CUDA empata (1,06×) y OpenCL sobre la Radeon integrada pierde (0,63×).

## Para recordar

- **Paralelismo de datos con costo fijo:** la GPU conviene recién cuando hay trabajo suficiente para amortizar mover los datos y lanzar los kernels (ley de Amdahl aplicada a la parte no paralelizable).
- **Medir trabajo asíncrono exige sincronizar:** eventos CUDA y profiling OpenCL miden en el dispositivo. El reloj del host solo vale después de esperar.
- **Medir bien exige serializar:** un solo proceso, backends de a uno y warmup afuera.
