# Spec Delta

## Purpose

Ejecuta el algoritmo de fotomosaico en GPUs mediante OpenCL (AMD u otras, incluida una NVIDIA), cumpliendo el contrato de backend y midiendo por separado cómputo y transferencias.

## ADDED Requirements

### Requirement: Selección de dispositivo OpenCL
El backend OpenCL MUST considerar solo dispositivos de tipo GPU de todas las plataformas. Si hay varios, MUST priorizar los de vendor AMD; entre los restantes, el primero en orden de plataforma y dispositivo.

#### Scenario: AMD y NVIDIA en la misma máquina
- **WHEN** hay una plataforma NVIDIA y una AMD, cada una con una GPU
- **THEN** el backend OpenCL usa la GPU AMD

#### Scenario: Solo NVIDIA
- **WHEN** la única GPU con OpenCL es una NVIDIA
- **THEN** el backend OpenCL usa esa GPU, y se puede comparar con el backend CUDA sobre la misma placa

#### Scenario: Solo dispositivos CPU
- **WHEN** las plataformas OpenCL solo exponen dispositivos de tipo CPU
- **THEN** el backend OpenCL se reporta como no disponible con motivo "sin GPU OpenCL"

### Requirement: Datos residentes en el dispositivo
Teselas, descriptores, normas, distancias y top-k MUST permanecer en memoria del dispositivo entre etapas. Dentro de las etapas comparadas, la única copia device→host MUST ser la de la imagen final.

#### Scenario: Trabajo completo
- **WHEN** termina un trabajo OpenCL
- **THEN** la única transferencia device→host medida es la imagen final

### Requirement: Buffers de host con ALLOC_HOST_PTR
Las transferencias host↔device MUST usar buffers de staging creados con `ALLOC_HOST_PTR` y mapeados para escribir o leer desde el host.

#### Scenario: Subida de teselas
- **WHEN** se suben `tiles_src` al dispositivo
- **THEN** los datos se escriben en un buffer de staging `ALLOC_HOST_PTR` mapeado y se copian desde él al buffer del dispositivo

### Requirement: Una única command queue con profiling
Todas las operaciones de un trabajo MUST encolarse en orden en una única command queue creada con profiling habilitado.

#### Scenario: Cola en orden
- **WHEN** se ejecuta un trabajo OpenCL
- **THEN** todas sus operaciones usan la misma cola, sin ejecución fuera de orden

### Requirement: Medición por eventos de profiling
El tiempo de cada etapa comparada MUST ser la diferencia entre el inicio del primer comando de la etapa y el fin del último, según los contadores de profiling de sus eventos. Las transferencias MUST medirse igual, por separado, y el total con reloj de pared hasta terminar la lectura de la imagen final.

#### Scenario: Etapa con varios kernels
- **WHEN** la etapa de matching lanza `sq_norms`, y luego `distances_tiled` y `topk_rows` por cada bloque
- **THEN** su tiempo va desde el inicio de `sq_norms` hasta el fin del último `topk_rows`

### Requirement: Bloques del matching según memoria del dispositivo
Como OpenCL no informa la memoria libre de forma estándar, el tamaño de bloque MUST calcularse a partir de una fracción configurada de la memoria global del dispositivo descontando los buffers reservados, y MUST respetar el tamaño máximo de una reserva individual del dispositivo. Si el dispositivo ofrece una consulta de memoria libre, MUST usarse.

#### Scenario: Límite de reserva individual
- **WHEN** la memoria global alcanza para 50.000 filas pero la reserva máxima individual solo para 20.000
- **THEN** el bloque de matching es de a lo sumo 20.000 celdas

### Requirement: Top-k disponible para validación
El backend MUST devolver `topk_idx` en el resultado leyéndolo del dispositivo después de cerrar la medición, sin que esa lectura se cuente en los tiempos ni en las transferencias.

#### Scenario: Lectura de validación
- **WHEN** termina un trabajo OpenCL
- **THEN** el resultado incluye `topk_idx` y el total medido no incluye su lectura
