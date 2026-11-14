# algoritmo-fotomosaico Specification

## Purpose

Define el algoritmo de fotomosaico de forma independiente del backend, para que CUDA, OpenCL y CPU secuencial resuelvan el mismo problema y la diferencia observable sea el tiempo, salvo pequeñas diferencias de punto flotante.

## Requirements
### Requirement: Parámetros del trabajo
Un trabajo MUST definirse con: `cols` (columnas de la grilla, entero dentro de un rango configurado), `tile_px` (16, 32 o 64), `k` (entero de 1 a 16, por defecto 5), `alpha` (real en [0, 1], por defecto 1.0) y `seed` (entero no negativo). El sistema MUST rechazar parámetros fuera de rango antes de ejecutar, y MUST rechazar `k > N`.

#### Scenario: tile_px inválido
- **WHEN** se pide un trabajo con `tile_px = 48`
- **THEN** el trabajo se rechaza indicando los valores permitidos (16, 32, 64)

#### Scenario: k mayor que la cantidad de teselas
- **WHEN** el lote tiene 3 teselas y se pide `k = 5`
- **THEN** el trabajo se rechaza indicando que `k` no puede superar N

### Requirement: Redimensionado de teselas
Cada tesela de 128×128 MUST reducirse a `tile_px`×`tile_px` promediando bloques de `f×f` píxeles por canal, con `f = 128 / tile_px`, y redondeando el promedio al entero más cercano. El resultado es `tiles_px [N, tile_px, tile_px, 3]` uint8.

#### Scenario: Bloque uniforme
- **WHEN** un bloque de 4×4 (tile_px = 32) tiene todos sus píxeles en (10, 20, 30)
- **THEN** el píxel de salida es (10, 20, 30)

#### Scenario: Redondeo hacia el más cercano
- **WHEN** un bloque de 2×2 (tile_px = 64) tiene valores 0, 1, 1, 1 en un canal
- **THEN** el valor de salida es 1 (promedio 0,75)

### Requirement: Conversión sRGB a CIELAB
La conversión de color MUST ser la estándar sRGB→CIELAB: normalizar cada canal a [0, 1] y linealizarlo con la curva gamma de sRGB; aplicar la matriz sRGB→XYZ (iluminante D65) y dividir por el blanco D65; aplicar `f(t) = ∛t` si `t > (6/29)³` y `f(t) = t / (3·(6/29)²) + 4/29` si no; y calcular L = 116·f(Y) − 16, a = 500·(f(X) − f(Y)), b = 200·(f(Y) − f(Z)). El cálculo MUST hacerse en float32.

#### Scenario: Blanco
- **WHEN** se convierte el color sRGB (255, 255, 255)
- **THEN** el resultado es L = 100, a = 0, b = 0 con tolerancia 0,01

#### Scenario: Rojo puro
- **WHEN** se convierte el color sRGB (255, 0, 0)
- **THEN** el resultado es L ≈ 53,24, a ≈ 80,09, b ≈ 67,20 con tolerancia 0,05

#### Scenario: Negro
- **WHEN** se convierte el color sRGB (0, 0, 0)
- **THEN** el resultado es L = 0, a = 0, b = 0 con tolerancia 0,01

### Requirement: Descriptor de tesela
El descriptor de cada tesela MUST ser una miniatura de 8×8 en Lab calculada sobre la tesela de 128×128: para cada bloque de 16×16 píxeles se promedian los valores sRGB de cada canal y el promedio se convierte a Lab. El descriptor tiene 192 floats ordenados como `[fila][columna][canal]` de la miniatura. El resultado es `tile_desc [N, 192]` float32.

#### Scenario: Tesela de color uniforme
- **WHEN** una tesela es entera del color (255, 0, 0)
- **THEN** sus 64 posiciones del descriptor valen el Lab del rojo puro

### Requirement: Descriptor de celda
Para cada una de las `M = rows·cols` celdas de la grilla, el descriptor MUST obtenerse convirtiendo a Lab, con la misma conversión, cada uno de los 64 píxeles del bloque 8×8 correspondiente de `target_src`, en el mismo orden `[fila][columna][canal]`. El resultado es `cell_desc [M, 192]` float32, con las celdas en orden de filas (`celda = fila · cols + columna`).

#### Scenario: Celda de la esquina inferior derecha
- **WHEN** la grilla es de 3 filas por 4 columnas
- **THEN** la celda 11 corresponde a los píxeles `[16:24, 24:32]` de `target_src`

### Requirement: Distancia entre descriptores
La distancia entre una celda `c` y una tesela `t` MUST ser la euclídea al cuadrado calculada como `(‖c‖² + ‖t‖²) − 2·(c·t)`, calculada en float32. Las normas de las teselas MUST calcularse una sola vez por trabajo.

#### Scenario: Descriptores idénticos
- **WHEN** una celda y una tesela tienen el mismo descriptor
- **THEN** su distancia es 0 o un valor de magnitud despreciable producto del redondeo en float32

### Requirement: Top-k con desempate determinista
Para cada celda, el sistema MUST obtener los `k` índices de tesela de menor distancia, ordenados de mejor a peor, junto con sus distancias. El orden MUST ser lexicográfico por (distancia, índice de tesela): ante igual distancia gana el índice menor. Los resultados son `topk_idx [M, k]` int32 y `topk_dist [M, k]` float32.

#### Scenario: Empate exacto
- **WHEN** las teselas 7 y 3 son idénticas y son las más cercanas a una celda
- **THEN** `topk_idx` de esa celda empieza con 3 y luego 7

#### Scenario: Teselas duplicadas en todo el lote
- **WHEN** todas las teselas del lote son idénticas y `k = 4`
- **THEN** cada fila de `topk_idx` es `[0, 1, 2, 3]`

### Requirement: Procesamiento por bloques de celdas
El matching MUST poder procesarse por bloques de celdas (chunks) para acotar la memoria de la matriz parcial de distancias `[m_chunk, N]`. El resultado MUST ser idéntico para cualquier tamaño de bloque.

#### Scenario: Distintos tamaños de bloque
- **WHEN** el mismo trabajo se ejecuta con bloques de 16 celdas y con un único bloque de M celdas
- **THEN** `topk_idx` y `topk_dist` son idénticos

### Requirement: Selección pseudoaleatoria entre candidatos
El sistema MUST generar en el host, una vez por trabajo, un array `choice [M]` de enteros uniformes en `[0, k)` con un generador pseudoaleatorio reproducible inicializado con `seed`. La tesela asignada a la celda `i` es `topk_idx[i, choice[i]]`. El mismo `choice` MUST usarse para todos los backends de un trabajo, y su generación no forma parte de los tiempos comparados.

#### Scenario: Misma semilla
- **WHEN** se ejecuta dos veces el mismo trabajo con `seed = 42`
- **THEN** los dos `choice` son idénticos

#### Scenario: k igual a 1
- **WHEN** `k = 1`
- **THEN** todos los valores de `choice` son 0 y cada celda recibe su mejor tesela

### Requirement: Composición de la imagen
La imagen final MUST medir `cols·tile_px` de ancho por `rows·tile_px` de alto. Cada píxel de salida MUST tomar el píxel correspondiente de la tesela asignada a su celda en `tiles_px`. Si `alpha < 1`, MUST mezclarse con el color objetivo, obtenido ampliando el bloque 8×8 de la celda a `tile_px` por vecino más cercano, como `salida = round(alpha·tesela + (1 − alpha)·objetivo)`.

#### Scenario: Sin mezcla
- **WHEN** `alpha = 1.0`
- **THEN** cada bloque de la imagen final es una copia exacta de la tesela asignada en `tiles_px`

#### Scenario: Solo objetivo
- **WHEN** `alpha = 0.0` y `tile_px = 32`
- **THEN** la imagen final es `target_src` ampliada ×4 por vecino más cercano

#### Scenario: Mezcla a la mitad
- **WHEN** `alpha = 0.5`, el píxel de la tesela vale 200 y el del objetivo 100 en un canal
- **THEN** el valor de salida es 150

