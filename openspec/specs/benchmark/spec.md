# benchmark Specification

## Purpose

Mide de forma reproducible y sin interfaz cómo escalan los backends con el tamaño del problema, para sostener con datos la conclusión del TP, incluido el caso en que la GPU no conviene.

## Requirements
### Requirement: Ejecución sin interfaz
El benchmark MUST poder ejecutarse con un comando de línea sin levantar la aplicación web, y MUST usar por defecto todos los backends disponibles, permitiendo elegir un subconjunto. Antes de medir MUST informar el estado de cada backend y su tiempo de inicialización.

#### Scenario: Máquina solo con CPU
- **WHEN** se ejecuta el benchmark en una máquina sin GPU
- **THEN** informa CUDA y OpenCL como no disponibles con su motivo y mide solo CPU secuencial

#### Scenario: Subconjunto de backends
- **WHEN** se ejecuta pidiendo solo CUDA y CPU
- **THEN** OpenCL no se mide aunque esté disponible

### Requirement: Grilla de tamaños configurable
El benchmark MUST medir todas las combinaciones de una lista de N y una lista de M, por defecto N ∈ {100, 1.000, 5.000} y M ∈ {1.000, 10.000, 40.000}, ambas configurables, junto con `tile_px`, `k` y `alpha`.

#### Scenario: Grilla por defecto
- **WHEN** se ejecuta sin opciones
- **THEN** se miden las 9 combinaciones de N y M por cada backend disponible

### Requirement: Datos sintéticos reproducibles
El benchmark MUST generar teselas y objetivo sintéticos a partir de una semilla, con variedad de colores suficiente para que el top-k no sea trivial, de modo que dos ejecuciones con la misma semilla midan exactamente los mismos datos. La grilla del objetivo MUST tener exactamente M celdas.

#### Scenario: Misma semilla
- **WHEN** se ejecuta dos veces con la misma semilla
- **THEN** los `topk_idx` obtenidos en cada tamaño son idénticos entre ejecuciones

### Requirement: Repeticiones y estadística
Cada medición MUST repetirse una cantidad configurable de veces (por defecto 3) después del warmup, y MUST informar la mediana y el mínimo del total y de cada etapa.

#### Scenario: Tres repeticiones
- **WHEN** se mide CUDA con N = 1.000 y M = 10.000
- **THEN** la tabla muestra la mediana y el mínimo de tres ejecuciones

### Requirement: Límite para CPU secuencial
El benchmark MUST omitir las combinaciones cuya duración estimada en CPU secuencial supere un máximo configurable, e informarlas como "omitido (estimado X s)" en la tabla, el CSV y el gráfico.

#### Scenario: Combinación más grande
- **WHEN** N = 5.000, M = 40.000 y la estimación de CPU supera el máximo configurado
- **THEN** esa combinación de CPU no se ejecuta y figura como omitida con su estimación

### Requirement: Verificación en cada tamaño
En cada combinación, el benchmark MUST comparar `topk_idx` e imagen final de cada backend contra la referencia (CPU secuencial si se ejecutó, si no el primer backend) e informar la cantidad de celdas distintas.

#### Scenario: Todo coincide
- **WHEN** todos los backends coinciden en todos los tamaños
- **THEN** el reporte indica "verificación: resultados idénticos en todas las combinaciones"

### Requirement: Reporte en tabla, CSV y gráfico
El benchmark MUST imprimir una tabla Markdown con los tiempos por backend y tamaño, MUST escribir un CSV con todas las mediciones (backend, dispositivo, N, M, M·N, repetición, tiempos por etapa, transferencias y total) y MUST generar un gráfico PNG del tiempo total en función de M·N por backend en escala log-log.

#### Scenario: Archivos de salida
- **WHEN** termina un benchmark con directorio de salida `resultados/`
- **THEN** existen en él el CSV y el PNG, y la consola muestra la tabla

### Requirement: Speedup y punto de cruce
Si se midió CPU secuencial, el reporte MUST incluir el speedup total de cada backend GPU por tamaño y, para cada backend GPU, el menor M·N medido a partir del cual su total es menor que el de la CPU, o indicar que en ningún tamaño medido la GPU fue más lenta.

#### Scenario: GPU más lenta en el tamaño más chico
- **WHEN** con N = 100 y M = 1.000 el total de CUDA es mayor que el de CPU por el costo de transferencias
- **THEN** el reporte muestra un speedup menor a 1× en ese tamaño e indica a partir de qué M·N CUDA supera a la CPU
