# backend-cuda Specification

## Purpose

Ejecuta el algoritmo de fotomosaico en GPUs NVIDIA mediante CUDA, cumpliendo el contrato de backend y midiendo por separado cómputo y transferencias.

## Requirements
### Requirement: Contexto CUDA explícito
El backend CUDA MUST crear su contexto explícitamente dentro del proceso que lo usa, sin inicialización automática al importar, y MUST liberarlo al cerrar el backend.

#### Scenario: Cierre ordenado
- **WHEN** se cierra el proceso que tiene el backend CUDA
- **THEN** el contexto se libera antes de terminar y no quedan mensajes de error del driver

#### Scenario: Importar sin GPU
- **WHEN** se importa el módulo del backend CUDA en una máquina sin GPU NVIDIA
- **THEN** la importación no falla y el backend se reporta como no disponible recién al intentar inicializarlo

### Requirement: Datos residentes en el dispositivo
Teselas, descriptores, normas, distancias y top-k MUST permanecer en memoria del dispositivo entre etapas. Dentro de las etapas comparadas, la única copia device→host MUST ser la de la imagen final.

#### Scenario: Trabajo completo
- **WHEN** termina un trabajo CUDA
- **THEN** las transferencias host→device son `tiles_src`, `target_src` y `choice`, y la única device→host medida es la imagen final

### Requirement: Memoria pinned para transferencias
Las transferencias host↔device MUST usar memoria page-locked del host. Si no se puede reservar memoria page-locked del tamaño necesario, el backend MUST usar memoria paginable e informarlo en el resultado.

#### Scenario: Reserva pinned rechazada
- **WHEN** el sistema no puede reservar memoria page-locked para la imagen final
- **THEN** el trabajo se completa con memoria paginable y el resultado indica "transferencia sin memoria pinned"

### Requirement: Un único stream por trabajo
Todas las copias y lanzamientos de kernels de un trabajo MUST encolarse en orden en un único stream.

#### Scenario: Orden de operaciones
- **WHEN** se ejecuta un trabajo CUDA
- **THEN** ninguna operación del trabajo se encola en otro stream ni en el stream por defecto

### Requirement: Medición con eventos CUDA
Los tiempos de cada etapa comparada y de cada grupo de transferencias MUST medirse con pares de eventos CUDA registrados en el stream del trabajo, y el total MUST medirse con reloj de pared hasta sincronizar el stream después de la copia de la imagen final.

#### Scenario: Tiempo de una etapa
- **WHEN** termina la etapa de matching
- **THEN** su tiempo es el transcurrido entre el evento registrado antes del primer kernel de la etapa y el registrado después del último

### Requirement: Bloques del matching según memoria libre
El tamaño del bloque de celdas del matching MUST calcularse a partir de la memoria libre del dispositivo después de reservar los demás buffers, dejando un margen configurado. Si ni un bloque mínimo entra en memoria, el trabajo MUST fallar con error "memoria insuficiente".

#### Scenario: GPU con poca memoria
- **WHEN** la memoria libre alcanza para 1.000 filas de distancias
- **THEN** el matching se procesa en bloques de a lo sumo 1.000 celdas y el resultado es idéntico al de procesar todas las celdas en un único bloque

### Requirement: Top-k disponible para validación
El backend MUST devolver `topk_idx` en el resultado copiándolo al host después de cerrar la medición, sin que esa copia se cuente en los tiempos ni en las transferencias.

#### Scenario: Copia de validación
- **WHEN** termina un trabajo CUDA
- **THEN** el resultado incluye `topk_idx` y el total medido no incluye su copia

