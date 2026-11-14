# Spec Delta

## Purpose

Ejecuta un mismo trabajo en CPU y en GPU bajo condiciones idénticas y presenta juntos sus mosaicos, sus tiempos, el speedup de la GPU respecto de la CPU y la verificación de que ambos produjeron el mismo resultado.

## ADDED Requirements

### Requirement: Opción "Ambas" según el hardware
El paso 3 de la interfaz MUST ofrecer, además de CPU y GPU, la opción "Ambas (CPU y GPU)". MUST poder elegirse solo si hay una GPU disponible; si no la hay, MUST verse deshabilitada con el motivo. La GPU usada MUST ser la misma que la opción GPU (CUDA con una placa NVIDIA, OpenCL en otro caso). El servidor MUST rechazar un pedido "Ambas" sin GPU disponible, sin ejecutarlo solo en CPU.

#### Scenario: Máquina sin GPU
- **WHEN** no hay GPU disponible
- **THEN** "Ambas" se ve deshabilitada con el motivo y solo se puede elegir CPU

#### Scenario: Máquina con NVIDIA
- **WHEN** CUDA está disponible y se elige "Ambas"
- **THEN** el trabajo corre con CUDA y con CPU, y con ningún otro backend

### Requirement: Condiciones idénticas
Los dos backends de una comparación MUST recibir los mismos `tiles_src`, `target_src`, parámetros y `choice`. La etapa común de carga MUST ejecutarse una sola vez por comparación.

#### Scenario: Carga única
- **WHEN** se ejecuta con "Ambas"
- **THEN** la carga común se informa una sola vez y los dos backends usan sus arrays

### Requirement: Ejecución secuencial, GPU primero
Los backends de una comparación MUST ejecutarse de a uno, nunca en simultáneo, primero la GPU y después la CPU. La interfaz MUST mostrar el progreso de cada uno.

#### Scenario: GPU terminada, CPU en curso
- **WHEN** la GPU terminó y la CPU sigue en curso
- **THEN** la barra de la GPU está completa y la barra de progreso de la CPU avanza

### Requirement: Mosaicos lado a lado
Al terminar, la pantalla de resultado MUST mostrar los dos mosaicos lado a lado, con el nombre del backend y el dispositivo, cada uno con su descarga en PNG y JPEG. El zoom y el desplazamiento de uno MUST aplicarse al otro.

#### Scenario: Zoom sincronizado
- **WHEN** se acerca una zona del mosaico de la GPU
- **THEN** el mosaico de la CPU muestra la misma zona con el mismo aumento

### Requirement: Estadísticas comparativas
Si se ejecutó con "Ambas", "Ver estadísticas" MUST mostrar las estadísticas de los dos backends en forma comparativa: la tabla de tiempos con una columna por backend y un gráfico de barras agrupadas con el tiempo de cada etapa comparada, de las transferencias y del total, que permita alternar entre escala lineal y logarítmica.

#### Scenario: Escala logarítmica
- **WHEN** CPU tarda 30.000 ms en el matching, la GPU 150 ms, y se activa la escala logarítmica
- **THEN** ambas barras se distinguen y el eje indica la escala logarítmica

### Requirement: Speedup de la GPU respecto de la CPU
Las estadísticas comparativas MUST mostrar el speedup `tiempo CPU / tiempo GPU` por etapa comparada y para el total (que incluye las transferencias de la GPU), y "—" donde falte un tiempo o sea cero.

#### Scenario: Speedup del matching
- **WHEN** CPU tarda 30.000 ms en el matching y la GPU 150 ms
- **THEN** el speedup en matching se muestra como "200×"

### Requirement: Verificación de resultados
Al terminar, el sistema MUST comparar `topk_idx` y la imagen final de la GPU contra los de la CPU. Si todo coincide, las estadísticas MUST mostrar "Resultados idénticos ✓"; si no, la cantidad de celdas que difieren. Una celda difiere si su fila de `topk_idx` o su bloque de la imagen no son idénticos.

#### Scenario: Resultados iguales
- **WHEN** CPU y GPU producen el mismo `topk_idx` y la misma imagen
- **THEN** se muestra "Resultados idénticos ✓"

#### Scenario: Diferencias por punto flotante
- **WHEN** la GPU (OpenCL) difiere de la CPU en el top-k de 3 celdas
- **THEN** se muestra "OpenCL: 3 celdas difieren de CPU (diferencias de punto flotante en casi-empates)"

### Requirement: Falla de la GPU aislada
Si la GPU falla durante la comparación, la CPU MUST ejecutarse igual, y la falla MUST mostrarse con su motivo. La pantalla de resultado MUST mostrar solo el mosaico de la CPU, y las estadísticas MUST mostrar sus tiempos indicando que no hubo comparación.

#### Scenario: GPU sin memoria
- **WHEN** en una comparación la GPU falla por memoria insuficiente
- **THEN** la CPU termina, se muestra "GPU falló: memoria insuficiente" y las estadísticas muestran solo los tiempos de CPU con el aviso "sin comparación"

### Requirement: Estimación de la comparación
La estimación de duración de CPU y la confirmación de trabajos largos MUST aplicarse a "Ambas" igual que a una ejecución en CPU.

#### Scenario: Comparación larga
- **WHEN** la estimación de CPU de la comparación supera el umbral configurado
- **THEN** se pide confirmación antes de ejecutar
