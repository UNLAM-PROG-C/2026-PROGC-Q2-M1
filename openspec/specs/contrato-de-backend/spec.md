# contrato-de-backend Specification

## Purpose

Fija la interfaz y las garantías que cumple todo backend de fotomosaico (CPU secuencial, CUDA, OpenCL), para que el resto del sistema los use de forma intercambiable y sus tiempos sean comparables.

## Requirements
### Requirement: Interfaz común de backend
Todo backend MUST exponer un nombre, el nombre del dispositivo en que corre, una operación de inicialización (`warmup`) y una operación de ejecución que recibe `tiles_src`, `target_src`, los parámetros, `choice` y un callback de progreso, y devuelve un resultado con la imagen final `[rows·tile_px, cols·tile_px, 3]` uint8, `topk_idx [M, k]` int32 y los tiempos medidos.

#### Scenario: Backends intercambiables
- **WHEN** el mismo código cliente ejecuta un trabajo con dos backends distintos
- **THEN** ambos se invocan de la misma forma y devuelven resultados con la misma estructura

### Requirement: Inicialización excluida de la comparación
La compilación de kernels, la compilación JIT y cualquier otro costo de preparación único MUST ocurrir en `warmup`, antes del primer trabajo. Su duración MUST medirse e informarse como "tiempo de inicialización" del backend y MUST NOT sumarse a los tiempos de ningún trabajo.

#### Scenario: Primer trabajo después de iniciar
- **WHEN** se ejecuta el primer trabajo con un backend ya inicializado
- **THEN** sus tiempos por etapa no incluyen compilación, y el tiempo de inicialización se informa por separado

### Requirement: Tiempos por etapa
Cada ejecución MUST informar, en milisegundos: preparación de teselas, descriptores del objetivo, matching + top-k, composición, transferencias host→device, transferencias device→host y total de punta a punta. El total MUST medirse con reloj de pared desde el inicio de la ejecución hasta que la imagen final está disponible en memoria del host. Los backends sin transferencias MUST informarlas como "no aplica", no como cero.

#### Scenario: Tiempos de un backend CPU
- **WHEN** se ejecuta un trabajo con el backend CPU secuencial
- **THEN** se informan las cuatro etapas y el total, y las transferencias figuran como "no aplica"

### Requirement: Reporte de progreso
Durante la ejecución, el backend MUST invocar el callback de progreso con el nombre de la etapa en curso y una fracción entre 0 y 1, al menos al empezar y al terminar cada etapa y por cada bloque de celdas procesado en el matching. El reporte de progreso MUST NOT forzar sincronizaciones dentro de una etapa que alteren su tiempo medido más allá de los límites entre bloques.

#### Scenario: Matching en varios bloques
- **WHEN** el matching se procesa en 10 bloques de celdas
- **THEN** el callback recibe al menos 10 actualizaciones crecientes para la etapa de matching

### Requirement: Equivalencia de resultados entre backends
Con los mismos `tiles_src`, `target_src`, parámetros y `choice`, todo backend MUST producir resultados equivalentes a los del backend CPU secuencial, que actúa como referencia: descriptores y `topk_dist` iguales dentro de una tolerancia configurada, y `topk_idx` idéntico en al menos un porcentaje mínimo configurado de las celdas. Las diferencias de punto flotante se aceptan y solo aparecen en casi-empates de distancia.

#### Scenario: Conjunto sintético pequeño
- **WHEN** se ejecuta un conjunto sintético con todos los backends disponibles
- **THEN** descriptores y `topk_dist` coinciden con los de CPU dentro de la tolerancia, y `topk_idx` coincide en al menos el porcentaje mínimo de celdas

#### Scenario: Celda con casi-empate
- **WHEN** dos teselas están a distancias de una celda que difieren menos que la tolerancia
- **THEN** que un backend elija una y otro la otra no se considera un error

### Requirement: Errores de ejecución aislados
Si un backend falla durante un trabajo (por ejemplo, falta de memoria), MUST informar el error con un mensaje descriptivo sin dejar el proceso en un estado inválido, de modo que se puedan ejecutar trabajos posteriores.

#### Scenario: Falta de memoria en el dispositivo
- **WHEN** un trabajo no entra en la memoria del dispositivo
- **THEN** el trabajo termina con error "memoria insuficiente" y el backend sigue disponible para un trabajo más chico

