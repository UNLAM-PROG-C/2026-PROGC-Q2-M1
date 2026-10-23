# Spec Delta

## Purpose

Define el conjunto de kernels de GPU que implementan el algoritmo de fotomosaico, idéntico en CUDA y OpenCL en lógica, descomposición en hilos y tamaños de bloque, para que la comparación entre ambas APIs y contra CPU sea justa y reproducible.

## ADDED Requirements

### Requirement: Mismo conjunto de kernels en ambas APIs
CUDA y OpenCL MUST implementar los mismos siete kernels (`resize_tiles`, `tile_descriptors`, `cell_descriptors`, `sq_norms`, `distances_tiled`, `topk_rows`, `compose`) con la misma lógica, los mismos argumentos en el mismo orden y el mismo tamaño de bloque/work-group por kernel.

#### Scenario: Revisión de paridad
- **WHEN** se comparan `kernels/mosaic.cu` y `kernels/mosaic.cl`
- **THEN** cada kernel existe en ambos archivos con la misma firma lógica y el mismo mapeo de hilos, y solo difieren los calificadores propios de cada API

#### Scenario: Tamaños de bloque compartidos
- **WHEN** se lanza cualquier kernel en CUDA y en OpenCL
- **THEN** el tamaño de bloque y de work-group sale de la misma constante del proyecto

### Requirement: Descomposición en hilos
Cada kernel MUST asignar el trabajo así: `resize_tiles`, un hilo por píxel de salida (tesela, y, x); `tile_descriptors`, un hilo por (tesela, celda de 8×8); `cell_descriptors`, un hilo por (celda, píxel de 8×8); `sq_norms`, un hilo por vector; `distances_tiled`, un hilo por elemento de la matriz de distancias del bloque, con *tiling* de 16×16 en memoria compartida/local; `topk_rows`, un bloque/work-group por celda; `compose`, un hilo por píxel de salida.

#### Scenario: Cantidad de hilos de compose
- **WHEN** se compone una imagen de 100 columnas, 75 filas y `tile_px = 32`
- **THEN** se lanzan al menos 3200 × 2400 hilos y cada uno escribe los 3 canales de un único píxel

### Requirement: Top-k por bloque de hilos
En `topk_rows`, cada hilo MUST recorrer una porción intercalada de la fila manteniendo su propio top-k ordenado, y los top-k parciales MUST combinarse en memoria compartida/local para obtener el top-k de la fila con el criterio (distancia, índice). El resultado MUST ser independiente de la cantidad de hilos del bloque.

#### Scenario: Empate entre porciones de hilos distintos
- **WHEN** las teselas 5 y 133 tienen la misma distancia mínima y las recorren hilos distintos
- **THEN** el top-k de la fila empieza con 5 y luego 133

### Requirement: Constantes compartidas
Los kernels MUST recibir las constantes del algoritmo (tamaños, constantes de color y tamaños de bloque) desde la misma fuente que usa el backend CPU, sin literales con significado de negocio en los archivos de kernels.

#### Scenario: Cambio de una constante
- **WHEN** se modifica una constante del algoritmo en la configuración del proyecto
- **THEN** los tres backends usan el nuevo valor sin editar los archivos de kernels

### Requirement: Kernels documentados en archivos separados
Los kernels MUST estar en `kernels/mosaic.cu` y `kernels/mosaic.cl`, separados del código Python, con un comentario por kernel que explique qué dato procesa cada hilo, cómo se calcula su índice y qué memoria compartida/local usa.

#### Scenario: Lectura de un kernel
- **WHEN** se lee `distances_tiled` en cualquiera de los dos archivos
- **THEN** el comentario explica qué fila y columna de la matriz calcula cada hilo y qué se carga en cada tile de memoria compartida/local

### Requirement: Selección dentro de la composición
`compose` MUST recibir `topk_idx` y `choice` y resolver en el dispositivo la tesela asignada a cada celda, de modo que `topk_idx` no necesite volver al host para componer la imagen.

#### Scenario: Composición sin copiar top-k al host
- **WHEN** se ejecuta un trabajo en GPU
- **THEN** las transferencias medidas device→host del trabajo son solo la de la imagen final
