# Spec Delta

## Purpose

Interfaz web local con la que una persona configura un fotomosaico, elige el backend, sigue el progreso, ve y descarga el resultado y lee los tiempos medidos, que son el objetivo didáctico de la aplicación.

## ADDED Requirements

### Requirement: Acceso solo local
El servidor MUST escuchar por defecto solo en `127.0.0.1`. Escuchar en otra interfaz MUST requerir configurarlo explícitamente.

#### Scenario: Configuración por defecto
- **WHEN** se inicia la aplicación sin configuración adicional
- **THEN** la interfaz es accesible en `http://127.0.0.1:<puerto>` y no desde otra máquina de la red

### Requirement: Parámetros del trabajo
La interfaz MUST permitir configurar columnas de la grilla, `tile_px` (16, 32 o 64), `k` (1 a 16), `alpha` (0 a 1) y semilla, con los valores por defecto del algoritmo. Los valores inválidos MUST señalarse junto al campo antes de enviar, y el servidor MUST volver a validarlos.

#### Scenario: k fuera de rango
- **WHEN** se escribe `k = 20`
- **THEN** el campo se marca como inválido con el rango permitido y el botón de ejecutar queda deshabilitado

### Requirement: Selector de backend con estado
La interfaz MUST listar todos los backends con su estado: disponible con el nombre del dispositivo y el tiempo de inicialización, o no disponible con el motivo. MUST ofrecer además "Automático". Los backends no disponibles MUST verse pero no poder elegirse, y CPU secuencial MUST poder elegirse siempre.

#### Scenario: Máquina solo con CPU
- **WHEN** no hay GPU
- **THEN** se ven "CUDA: no disponible (biblioteca no instalada)", "OpenCL: no disponible (sin GPU OpenCL)" y "CPU secuencial: siempre disponible", y solo CPU y Automático se pueden elegir

#### Scenario: Backend elegido y usado
- **WHEN** se elige "Automático" y se ejecuta
- **THEN** el resultado muestra qué backend y qué dispositivo se usaron

### Requirement: Información del problema
Con el lote y el objetivo subidos, la interfaz MUST mostrar N (teselas válidas), M (= filas · columnas), la cantidad de comparaciones de distancia M·N y el tamaño de la imagen final en píxeles y en MB sin comprimir, actualizados al cambiar los parámetros.

#### Scenario: Cambio de columnas
- **WHEN** N = 1.000, el objetivo es 4:3 y se pasa de 100 a 200 columnas
- **THEN** M pasa de 7.500 a 30.000 y M·N de 7,5 millones a 30 millones

### Requirement: Límite de tamaño de salida
Si la imagen final supera un límite de píxeles configurado, la interfaz MUST advertirlo y el servidor MUST rechazar el trabajo indicando el límite.

#### Scenario: Salida gigante
- **WHEN** los parámetros generan una imagen mayor al límite configurado
- **THEN** se muestra la advertencia y el botón de ejecutar queda deshabilitado

### Requirement: Estimación para CPU secuencial
Cuando el backend que se usaría es CPU secuencial, la interfaz MUST mostrar una estimación de duración basada en M·N, calibrada con una medición hecha al iniciar el worker. Si la estimación supera un umbral configurado, MUST pedir confirmación antes de ejecutar.

#### Scenario: Trabajo largo en CPU
- **WHEN** se elige CPU secuencial con M·N = 200 millones y la estimación supera el umbral
- **THEN** se muestra "CPU secuencial: tiempo estimado ~X min" y se pide confirmar antes de ejecutar

### Requirement: Progreso por etapa en vivo
Durante un trabajo, la interfaz MUST mostrar una barra de progreso por etapa (carga común, preparación de teselas, descriptores del objetivo, matching + top-k, composición), actualizada por WebSocket sin recargar la página. Si la página se recarga durante un trabajo, MUST recuperar el estado del trabajo en curso.

#### Scenario: Recarga durante el matching
- **WHEN** se recarga la página con un trabajo en la etapa de matching
- **THEN** la interfaz vuelve a mostrar el trabajo en curso con su progreso actual

### Requirement: Un solo trabajo desde la interfaz
Mientras haya un trabajo en curso, la interfaz MUST deshabilitar la ejecución en todas las pestañas abiertas, y MUST volver a habilitarla cuando el trabajo termine o falle.

#### Scenario: Dos pestañas
- **WHEN** se inicia un trabajo desde una pestaña
- **THEN** en la otra pestaña el botón de ejecutar se deshabilita mientras dure el trabajo

### Requirement: Vista previa con zoom
Al terminar, la interfaz MUST mostrar una vista previa del mosaico que permita acercar y desplazarse hasta ver teselas individuales, sin necesidad de cargar en el navegador la imagen completa cuando esta supera un tamaño configurado.

#### Scenario: Mosaico grande
- **WHEN** el resultado mide 12.800 × 9.600 píxeles
- **THEN** la vista previa carga una versión reducida y al acercar se pueden distinguir las teselas

### Requirement: Descarga del resultado
La interfaz MUST permitir descargar el mosaico en resolución completa en PNG y en JPEG.

#### Scenario: Descarga JPEG
- **WHEN** se pide la descarga en JPEG
- **THEN** se descarga un archivo `.jpg` con las dimensiones completas del mosaico

### Requirement: Tabla de tiempos
Al terminar un trabajo, la interfaz MUST mostrar una tabla con: carga común (indicando si se reutilizó), preparación de teselas, descriptores del objetivo, matching + top-k, composición, transferencias host→device (copia a staging y DMA), transferencias device→host, total del backend e inicialización del backend. Las filas que no aplican MUST mostrarse como "no aplica".

#### Scenario: Trabajo en CPU
- **WHEN** termina un trabajo con CPU secuencial
- **THEN** las filas de transferencias dicen "no aplica" y el resto tiene tiempos en ms

### Requirement: Errores visibles
Si un trabajo falla, la interfaz MUST mostrar el motivo informado por el worker y dejar la aplicación lista para otro trabajo.

#### Scenario: Memoria insuficiente en GPU
- **WHEN** un trabajo en CUDA falla por memoria insuficiente
- **THEN** se muestra "memoria insuficiente en el dispositivo" y se puede lanzar otro trabajo
