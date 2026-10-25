# Spec Delta

## MODIFIED Requirements

### Requirement: Lenguaje visual según el design system
La interfaz MUST seguir el design system de `TP-Integrador/frontend/DESIGN.md`: colores, tipografía, espaciado, radios y componentes MUST tomarse de sus tokens, con un único color de acento (Action Blue) para todo elemento interactivo, botones principales en forma de píldora, sin gradientes decorativos y sin sombras en tarjetas, botones o texto. La única sombra (la de producto) MUST reservarse para el mosaico resultante. Los componentes MUST NOT usar colores literales: MUST usar los tokens. Cada pantalla MUST tener como máximo un botón principal (píldora rellena); el resto de las acciones MUST ser secundarias.

#### Scenario: Acción principal
- **WHEN** se muestra el botón "Siguiente" o "Generar mosaico"
- **THEN** es una píldora Action Blue (#0066cc) con texto blanco que al presionarse se achica (`scale(0.95)`)

#### Scenario: Mosaico como producto
- **WHEN** se muestra el resultado
- **THEN** el mosaico aparece centrado sobre un bloque oscuro de borde a borde con la sombra de producto, y nada más en la pantalla tiene sombra

#### Scenario: Un solo botón principal en el resultado
- **WHEN** se muestra el resultado de un trabajo terminado
- **THEN** "Ver estadísticas" es el único botón principal, y "Descargar" es una píldora secundaria junto a los controles de zoom del mosaico

### Requirement: Errores visibles
Si un trabajo falla, la interfaz MUST mostrar el motivo informado por el worker dentro del paso Resultado, con el mismo fondo oscuro que un resultado exitoso, y ofrecer "Volver a empezar" con las imágenes cargadas.

#### Scenario: Memoria insuficiente en GPU
- **WHEN** un trabajo en GPU falla por memoria insuficiente
- **THEN** se muestra "memoria insuficiente en el dispositivo" y se puede lanzar otro trabajo sin volver a subir las imágenes

#### Scenario: Fallo dentro del paso Resultado
- **WHEN** el trabajo falló
- **THEN** la pantalla tiene el título "Resultado" sobre fondo oscuro, la bajada indica que no se pudo generar el mosaico y el motivo aparece en la línea de mensajes de la barra de acciones

### Requirement: Estadísticas con scroll
El paso de estadísticas MUST permitir scrollear la página cuando su contenido (banda de verificación, gráfico y tablas) supera el alto de la ventana, y MUST ofrecer "Atrás" hacia el resultado y "Volver a empezar" en la barra de acciones fija, visibles durante todo el scroll.

#### Scenario: Comparación en una ventana baja
- **WHEN** se muestran las estadísticas de una ejecución con "Ambas" en una ventana de 700 px de alto
- **THEN** la página scrollea hasta la tabla de tiempos y "Atrás" y "Volver a empezar" se ven abajo de la ventana en todo momento

## ADDED Requirements

### Requirement: Estructura común de los pasos
Todas las pantallas del stepper, incluidos el progreso y el resultado, MUST tener la misma estructura: un encabezado con el título y una bajada, el contenido y la barra de acciones. El título MUST ser el nombre del paso tal como lo muestra el stepper. La bajada MUST contener la instrucción del paso o su estado, incluidos los estados de carga, que MUST NOT reemplazar el título.

#### Scenario: Título del resultado
- **WHEN** se muestra el resultado de un trabajo con un mosaico
- **THEN** el título es "Resultado" y la bajada indica el backend, el dispositivo y el tamaño

#### Scenario: Título del resultado comparado
- **WHEN** se muestra el resultado de una ejecución con "Ambas"
- **THEN** el título es "Resultado", la bajada indica los dos backends y el tamaño, y cada mosaico indica su backend y su dispositivo en el pie

#### Scenario: Título durante la generación
- **WHEN** se está generando el mosaico
- **THEN** el título es "Generando", igual que en el stepper, y la bajada indica en qué backend se ejecuta

#### Scenario: Carga en la bajada
- **WHEN** se abre el paso 2 antes de recibir las reglas del backend
- **THEN** el título es "Parámetros" y la bajada dice "Conectando con el backend…"

### Requirement: Fondo según el tipo de paso
El fondo de cada pantalla MUST depender de lo que pasa en ella: claro donde la persona completa algo (imágenes, parámetros, forma de ejecución), parchment donde el sistema informa (generación y estadísticas) y oscuro solo en el resultado, salga bien o falle.

#### Scenario: Pasos de configuración
- **WHEN** se navega por los pasos 1, 2 y 3
- **THEN** los tres tienen el mismo fondo claro

#### Scenario: Resultado fallido
- **WHEN** el trabajo falló y se muestra el paso 4
- **THEN** el fondo es oscuro, igual que con un resultado exitoso

#### Scenario: Estadísticas
- **WHEN** se muestra el paso 5
- **THEN** el fondo es parchment, igual que durante la generación

### Requirement: Encabezado a la misma altura en todos los pasos
El título de cada paso MUST quedar a la misma distancia del stepper en todas las pantallas, incluido el resultado.

#### Scenario: De la ejecución al resultado
- **WHEN** en una ventana de 1440 × 900 px se pasa del paso 3 al paso 4
- **THEN** el título "Resultado" queda a la misma altura que tenía el título "Ejecución"

### Requirement: Barra de acciones fija
Las acciones de cada paso MUST estar en una barra fija abajo de la ventana, del mismo fondo que el paso y alineada con el ancho del contenido, de modo que los botones queden a la misma altura en todos los pasos, sin importar cuánto mida el contenido. El orden MUST ser: "Atrás" (si existe), la acción principal y las secundarias.

#### Scenario: Pasos de distinto alto
- **WHEN** en una ventana de 1440 × 900 px se pasa del paso 2 al paso 3
- **THEN** "Generar mosaico" queda a la misma altura que tenía "Siguiente" en el paso 2

#### Scenario: Contenido más alto que la ventana
- **WHEN** el contenido del paso supera el alto de la ventana y se scrollea
- **THEN** la barra de acciones sigue visible abajo de la ventana

#### Scenario: Orden de las acciones
- **WHEN** se muestra el paso 3 con un resultado previo de esta pestaña
- **THEN** la barra muestra, en este orden, "Atrás", "Generar mosaico" y "Ver resultado"

### Requirement: Línea de mensajes del paso
La barra de acciones MUST reservar una línea debajo de los botones para el motivo por el que no se puede avanzar o para un error general del paso (por ejemplo, el rechazo del trabajo o el límite de salida). Que el mensaje aparezca o desaparezca MUST NOT mover los botones. Los errores de un campo MUST mostrarse junto a ese campo.

#### Scenario: Aparece un motivo de bloqueo
- **WHEN** en el paso 1 se descarta la imagen objetivo
- **THEN** aparece "falta la imagen objetivo" debajo de "Siguiente" y el botón no cambia de posición

#### Scenario: Error al lanzar el trabajo
- **WHEN** el servidor rechaza el trabajo al apretar "Generar mosaico"
- **THEN** el motivo se muestra en la línea de mensajes de la barra de acciones

#### Scenario: Error de un campo
- **WHEN** las columnas tienen un valor inválido
- **THEN** el error se muestra debajo del campo de columnas, no en la barra de acciones

### Requirement: Contraste del texto secundario
El texto secundario (bajadas apagadas, ayudas, motivos de bloqueo, encabezados de tabla) MUST tener un contraste de al menos 4,5:1 sobre los fondos claro y parchment.

#### Scenario: Motivo de bloqueo sobre fondo claro
- **WHEN** se muestra "falta la imagen objetivo" en el paso 1
- **THEN** el texto tiene un contraste de al menos 4,5:1 contra el fondo
