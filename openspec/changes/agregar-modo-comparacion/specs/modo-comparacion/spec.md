# Spec Delta

## Purpose

Ejecuta un mismo trabajo con varios backends bajo condiciones idénticas y presenta juntos sus tiempos, el speedup de GPU respecto de CPU secuencial y la verificación de que todos produjeron el mismo resultado.

## ADDED Requirements

### Requirement: Selección de backends a comparar
La interfaz MUST permitir marcar qué backends disponibles incluir en la comparación, y MUST exigir al menos dos. Los backends no disponibles MUST verse pero no poder marcarse.

#### Scenario: Un solo backend marcado
- **WHEN** en modo comparar solo está marcado CUDA
- **THEN** el botón de ejecutar queda deshabilitado con el mensaje "elegí al menos dos backends"

#### Scenario: CPU y CUDA
- **WHEN** se marcan CPU secuencial y CUDA y se ejecuta
- **THEN** el trabajo corre con esos dos backends y con ningún otro

### Requirement: Condiciones idénticas
Todos los backends de una comparación MUST recibir los mismos `tiles_src`, `target_src`, parámetros y `choice`. La etapa común de carga MUST ejecutarse una sola vez por comparación.

#### Scenario: Carga única
- **WHEN** se compara CPU, CUDA y OpenCL
- **THEN** la carga común se informa una sola vez y los tres backends usan sus arrays

### Requirement: Ejecución secuencial en orden fijo
Los backends de una comparación MUST ejecutarse de a uno, nunca en simultáneo, en el orden CUDA, OpenCL, CPU secuencial (los que estén marcados). La interfaz MUST mostrar el progreso de cada uno y sus resultados a medida que termina.

#### Scenario: Resultados parciales
- **WHEN** CUDA terminó y CPU secuencial sigue en curso
- **THEN** ya se ven los tiempos y la imagen de CUDA, y la barra de progreso de CPU avanza

### Requirement: Gráfico de tiempos por etapa
Al terminar, la interfaz MUST mostrar un gráfico de barras agrupadas con el tiempo de cada etapa comparada, de las transferencias y del total para cada backend, y MUST permitir alternar entre escala lineal y logarítmica.

#### Scenario: Escala logarítmica
- **WHEN** CPU tarda 30.000 ms en el matching, CUDA 150 ms, y se activa la escala logarítmica
- **THEN** ambas barras se distinguen y el eje indica la escala logarítmica

### Requirement: Speedup respecto de CPU secuencial
Si la comparación incluye CPU secuencial, la interfaz MUST mostrar para cada backend GPU el speedup `tiempo CPU / tiempo GPU` por etapa comparada y para el total (que incluye las transferencias de la GPU). Si no incluye CPU, MUST indicar que el speedup requiere incluirla.

#### Scenario: Speedup del matching
- **WHEN** CPU tarda 30.000 ms en el matching y CUDA 150 ms
- **THEN** el speedup de CUDA en matching se muestra como "200×"

#### Scenario: Comparación sin CPU
- **WHEN** se comparan CUDA y OpenCL
- **THEN** se muestran los tiempos de ambos y el texto "incluí CPU secuencial para ver el speedup"

### Requirement: Verificación de resultados
Al terminar, el sistema MUST comparar `topk_idx` y la imagen final de cada backend contra la referencia (CPU secuencial si está incluida, si no el primer backend ejecutado). Si todo coincide, MUST mostrar "Resultados idénticos ✓"; si no, la cantidad de celdas que difieren por backend. Una celda difiere si su fila de `topk_idx` o su bloque de la imagen no son idénticos.

#### Scenario: Resultados iguales
- **WHEN** CPU, CUDA y OpenCL producen el mismo `topk_idx` y la misma imagen
- **THEN** se muestra "Resultados idénticos ✓"

#### Scenario: Diferencias por punto flotante
- **WHEN** OpenCL difiere de CPU en el top-k de 3 celdas
- **THEN** se muestra "OpenCL: 3 celdas difieren de CPU secuencial (diferencias de punto flotante en casi-empates)" y las demás verificaciones por separado

### Requirement: Imágenes lado a lado
La interfaz MUST mostrar las imágenes resultantes de todos los backends lado a lado, con el nombre del backend, y el zoom y desplazamiento de una MUST aplicarse a todas.

#### Scenario: Zoom sincronizado
- **WHEN** se acerca una zona de la imagen de CUDA
- **THEN** las imágenes de los demás backends muestran la misma zona con el mismo aumento

### Requirement: Fallas aisladas en la comparación
Si un backend falla durante la comparación, los demás MUST ejecutarse igual, y el backend fallido MUST mostrarse con su motivo y quedar fuera del gráfico, del speedup y de la verificación.

#### Scenario: OpenCL sin memoria
- **WHEN** en una comparación de los tres backends OpenCL falla por memoria insuficiente
- **THEN** CUDA y CPU terminan, se comparan entre sí y OpenCL se muestra como "falló: memoria insuficiente"

### Requirement: Estimación de la comparación
Si la comparación incluye CPU secuencial, la estimación de duración y la confirmación de trabajos largos de la interfaz MUST aplicarse igual que en una ejecución individual.

#### Scenario: Comparación larga
- **WHEN** la estimación de CPU de la comparación supera el umbral configurado
- **THEN** se pide confirmación antes de ejecutar
