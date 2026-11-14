# interfaz-web Specification

## Purpose

Interfaz web local de una sola pantalla, guiada por un stepper y con el lenguaje visual del design system del frontend, con la que una persona sube las imágenes, configura el fotomosaico, elige si ejecutarlo en CPU o en GPU, sigue el progreso, ve y descarga el resultado y consulta los tiempos medidos, que son el objetivo didáctico de la aplicación.

## Requirements
### Requirement: Acceso solo local
El backend y el frontend MUST escuchar por defecto solo en `127.0.0.1`. Escuchar en otra interfaz MUST requerir configurarlo explícitamente. El backend MUST aceptar peticiones de navegador (CORS y WebSocket) solo desde el origen configurado del frontend.

#### Scenario: Configuración por defecto
- **WHEN** se inicia la aplicación sin configuración adicional
- **THEN** la interfaz es accesible en `http://127.0.0.1:<puerto del frontend>` y no desde otra máquina de la red

#### Scenario: Origen no permitido
- **WHEN** una página servida desde otro origen llama a `POST /api/jobs`
- **THEN** el navegador bloquea la respuesta porque el backend no incluye ese origen en CORS

### Requirement: Stepper de tres pasos
La interfaz MUST guiar la configuración en tres pasos en este orden: (1) imágenes, (2) parámetros y (3) forma de ejecución. MUST mostrar en qué paso se está, permitir volver a un paso anterior sin perder lo cargado y habilitar "Siguiente" solo cuando los datos del paso son válidos.

#### Scenario: Paso incompleto
- **WHEN** en el paso 1 se cargó el lote pero no la imagen objetivo
- **THEN** "Siguiente" queda deshabilitado con el mensaje "falta la imagen objetivo"

#### Scenario: Volver atrás
- **WHEN** en el paso 3 se vuelve al paso 2 y se cambian las columnas
- **THEN** el lote y el objetivo siguen cargados y al avanzar se conserva la forma de ejecución elegida

### Requirement: Paso 1 — imágenes
El paso 1 MUST permitir cargar el lote de teselas (varios archivos o un `.zip`) y la imagen objetivo, mostrar el progreso de la subida y, al terminar, un resumen del lote (teselas aceptadas e ignoradas) con una muestra de miniaturas y una miniatura del objetivo.

#### Scenario: Lote subido
- **WHEN** se suben 200 JPEG y 3 archivos `.txt` como lote
- **THEN** se ve "200 teselas · 3 archivos ignorados" y una muestra de miniaturas del lote

### Requirement: Paso 2 — parámetros
El paso 2 MUST permitir configurar, con los valores por defecto del algoritmo y una ayuda contextual en cada campo: "Columnas de la grilla", "Resolución de cada tesela" (16, 32 o 64 px), "Opacidad de las teselas" (el `alpha` del algoritmo, presentado de 0 a 100 %) y "Semilla". La interfaz MUST NOT mostrar `k`; el servidor MUST usar `k = min(K por defecto, N)`. Los valores inválidos MUST señalarse junto al campo, y el servidor MUST volver a validarlos.

#### Scenario: Opacidad
- **WHEN** se elige "Opacidad de las teselas" = 60 %
- **THEN** el trabajo se envía con `alpha = 0.6`

#### Scenario: Columnas fuera de rango
- **WHEN** se escribe una cantidad de columnas mayor al máximo permitido
- **THEN** el campo se marca como inválido con el rango permitido y "Siguiente" queda deshabilitado

#### Scenario: Lote más chico que k
- **WHEN** el lote tiene 3 teselas válidas y el `k` por defecto es 5
- **THEN** el trabajo se ejecuta con `k = 3` sin que la persona tenga que configurarlo

### Requirement: Ayuda contextual de los parámetros
Junto a la etiqueta de cada parámetro del paso 2, la interfaz MUST mostrar un ícono chico de signo de pregunta. Al pasar el mouse por encima, MUST mostrar un texto breve que explique qué significa el parámetro y cómo afecta al mosaico. El texto MUST ocultarse al sacar el mouse, MUST mostrarse también al enfocar el ícono con el teclado y al tocarlo en pantallas táctiles, y MUST quedar asociado al campo para lectores de pantalla.

#### Scenario: Mouse sobre la ayuda
- **WHEN** se pasa el mouse sobre el signo de pregunta de "Opacidad de las teselas"
- **THEN** aparece el texto que explica la opacidad y desaparece al sacar el mouse

#### Scenario: Ayuda con teclado
- **WHEN** se llega con Tab al signo de pregunta de "Semilla"
- **THEN** se muestra su texto de ayuda y un lector de pantalla lo anuncia como descripción del campo

### Requirement: Textos de ayuda de los parámetros
Cada texto de ayuda MUST explicar en lenguaje no técnico qué controla el parámetro y qué se gana y se pierde al subirlo o bajarlo.

#### Scenario: Columnas de la grilla
- **WHEN** se muestra la ayuda de "Columnas de la grilla"
- **THEN** dice "Cantidad de teselas a lo ancho del mosaico. Más columnas dan más detalle, pero el mosaico tarda más y la imagen final es más grande. Las filas se calculan solas según la proporción de la imagen objetivo."

#### Scenario: Resolución de cada tesela
- **WHEN** se muestra la ayuda de "Resolución de cada tesela"
- **THEN** dice "Tamaño en píxeles con el que se dibuja cada tesela en el mosaico final. Más resolución da una imagen más nítida al hacer zoom, pero más pesada."

#### Scenario: Opacidad de las teselas
- **WHEN** se muestra la ayuda de "Opacidad de las teselas"
- **THEN** dice "Cuánto se ve la foto de cada tesela. Con 100 % se ven las fotos tal cual; con valores menores, cada tesela se tiñe con el color de esa zona de la imagen objetivo y el mosaico se parece más a ella."

#### Scenario: Semilla
- **WHEN** se muestra la ayuda de "Semilla"
- **THEN** dice "Número que fija las elecciones al azar entre teselas parecidas. Con la misma semilla y los mismos parámetros se obtiene exactamente el mismo mosaico; cambiala para ver otra variante."

### Requirement: Pantalla única guiada por el stepper
La interfaz MUST ser una única pantalla cuya navegación es solo el stepper: MUST NOT tener barra lateral (sidebar), menú de navegación global ni otras secciones a las que saltar. El stepper MUST quedar visible arriba durante los pasos 1 a 3, y la ejecución y el resultado MUST mostrarse en la misma pantalla, a continuación del paso 3.

#### Scenario: Navegación
- **WHEN** se abre la aplicación en un navegador de escritorio
- **THEN** solo se ven el stepper y el contenido del paso actual, sin sidebar ni menú global

#### Scenario: Pantalla angosta
- **WHEN** la ventana mide 400 px de ancho
- **THEN** el stepper se compacta (por ejemplo "Paso 2 de 3 · Parámetros") y no aparece ningún menú lateral ni hamburguesa

### Requirement: Lenguaje visual según el design system
La interfaz MUST seguir el design system de `TP-Integrador/frontend/DESIGN.md`: colores, tipografía, espaciado, radios y componentes MUST tomarse de sus tokens, con un único color de acento (Action Blue) para todo elemento interactivo, botones principales en forma de píldora, sin gradientes decorativos y sin sombras en tarjetas, botones o texto. La única sombra (la de producto) MUST reservarse para el mosaico resultante. Los componentes MUST NOT usar colores literales: MUST usar los tokens.

#### Scenario: Acción principal
- **WHEN** se muestra el botón "Siguiente" o "Generar mosaico"
- **THEN** es una píldora Action Blue (#0066cc) con texto blanco que al presionarse se achica (`scale(0.95)`)

#### Scenario: Mosaico como producto
- **WHEN** se muestra el resultado
- **THEN** el mosaico aparece centrado sobre un bloque oscuro de borde a borde con la sombra de producto, y nada más en la pantalla tiene sombra

### Requirement: Información del problema
En el paso 2, la interfaz MUST mostrar N (teselas válidas), M (= filas · columnas), la cantidad de comparaciones de distancia M·N y el tamaño de la imagen final en píxeles y en MB sin comprimir, actualizados al cambiar los parámetros.

#### Scenario: Cambio de columnas
- **WHEN** N = 1.000, el objetivo es 4:3 y se pasa de 100 a 200 columnas
- **THEN** M pasa de 7.500 a 30.000 y M·N de 7,5 millones a 30 millones

### Requirement: Límite de tamaño de salida
Si la imagen final supera un límite de píxeles configurado, la interfaz MUST advertirlo en el paso 2 y no dejar avanzar, y el servidor MUST rechazar el trabajo indicando el límite.

#### Scenario: Salida gigante
- **WHEN** los parámetros generan una imagen mayor al límite configurado
- **THEN** se muestra la advertencia y "Siguiente" queda deshabilitado

### Requirement: Paso 3 — forma de ejecución según el hardware
El paso 3 MUST ofrecer "CPU" y "GPU". CPU MUST poder elegirse siempre. La opción GPU MUST indicar qué API y qué dispositivo se van a usar, elegidos por el sistema según la placa disponible (CUDA con una placa NVIDIA, OpenCL en otro caso), sin que la persona elija entre CUDA y OpenCL. Si no hay GPU utilizable, GPU MUST verse deshabilitada con el motivo.

#### Scenario: Máquina con NVIDIA
- **WHEN** la máquina tiene una GeForce RTX 3060 con CUDA disponible
- **THEN** la opción GPU dice "GPU — CUDA (GeForce RTX 3060)"

#### Scenario: Máquina con GPU AMD o Apple
- **WHEN** CUDA no está disponible y OpenCL sí
- **THEN** la opción GPU dice "GPU — OpenCL (<nombre del dispositivo>)"

#### Scenario: Máquina sin GPU
- **WHEN** ni CUDA ni OpenCL están disponibles
- **THEN** GPU se ve deshabilitada con el motivo (por ejemplo "no se detectó una GPU compatible") y solo se puede elegir CPU

### Requirement: Estimación para CPU
Cuando la forma de ejecución incluye CPU, el paso 3 MUST mostrar una estimación de duración basada en M·N, calibrada con una medición hecha al iniciar el worker. Si la estimación supera un umbral configurado, MUST pedir confirmación antes de ejecutar.

#### Scenario: Trabajo largo en CPU
- **WHEN** se elige CPU con M·N = 200 millones y la estimación supera el umbral
- **THEN** se muestra "CPU: tiempo estimado ~X min" y se pide confirmar antes de ejecutar

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

### Requirement: Resultado con zoom
Al terminar, la interfaz MUST mostrar el fotomosaico, indicando qué forma de ejecución y qué dispositivo se usaron, con una vista que permita acercar y desplazarse hasta ver teselas individuales, sin necesidad de cargar en el navegador la imagen completa cuando esta supera un tamaño configurado.

#### Scenario: Mosaico grande
- **WHEN** el resultado mide 12.800 × 9.600 píxeles
- **THEN** la vista carga una versión reducida y al acercar se pueden distinguir las teselas

### Requirement: Descarga del resultado
La pantalla de resultado MUST permitir descargar el mosaico en resolución completa en PNG y en JPEG.

#### Scenario: Descarga JPEG
- **WHEN** se pide la descarga en JPEG
- **THEN** se descarga un archivo `.jpg` con las dimensiones completas del mosaico

### Requirement: Estadísticas a pedido
La pantalla de resultado MUST tener un botón "Ver estadísticas" que muestre la tabla de tiempos: carga común (indicando si se reutilizó), preparación de teselas, descriptores del objetivo, matching + top-k, composición, transferencias host→device (copia a staging y DMA), transferencias device→host, total del backend e inicialización del backend. Las filas que no aplican MUST mostrarse como "no aplica". Las estadísticas MUST NOT ocupar la pantalla hasta que se pidan.

#### Scenario: Trabajo en CPU
- **WHEN** termina un trabajo en CPU y se aprieta "Ver estadísticas"
- **THEN** las filas de transferencias dicen "no aplica" y el resto tiene tiempos en ms

### Requirement: Volver a empezar con las imágenes cargadas
La pantalla de resultado MUST ofrecer "Volver a empezar", que regresa al paso 1 con el lote y la imagen objetivo del trabajo anterior ya cargados (resumen y miniaturas), sin volver a subirlos. MUST permitir reemplazar cualquiera de los dos por separado. Los parámetros y la forma de ejecución MUST conservar los últimos valores usados. Esto MUST funcionar también después de recargar la página, mientras el backend conserve esas subidas.

#### Scenario: Repetir con otros parámetros
- **WHEN** se aprieta "Volver a empezar" y se avanza al paso 2 sin tocar las imágenes
- **THEN** no se sube ningún archivo y el trabajo siguiente reutiliza la carga del lote

#### Scenario: Cambiar solo el objetivo
- **WHEN** después de "Volver a empezar" se reemplaza la imagen objetivo
- **THEN** solo se sube el objetivo nuevo y el lote sigue siendo el anterior

#### Scenario: Recarga en la pantalla de resultado
- **WHEN** se recarga la página y se aprieta "Volver a empezar"
- **THEN** el paso 1 muestra el último lote y el último objetivo subidos

### Requirement: Errores visibles
Si un trabajo falla, la interfaz MUST mostrar el motivo informado por el worker y ofrecer "Volver a empezar" con las imágenes cargadas.

#### Scenario: Memoria insuficiente en GPU
- **WHEN** un trabajo en GPU falla por memoria insuficiente
- **THEN** se muestra "memoria insuficiente en el dispositivo" y se puede lanzar otro trabajo sin volver a subir las imágenes
