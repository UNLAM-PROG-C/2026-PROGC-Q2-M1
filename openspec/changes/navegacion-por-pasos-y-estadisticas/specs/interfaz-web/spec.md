# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: Stepper de tres pasos`
- TO: `### Requirement: Stepper de cinco pasos`

## MODIFIED Requirements

### Requirement: Stepper de cinco pasos
La interfaz MUST guiar el uso en cinco pasos en este orden: (1) imágenes, (2) parámetros, (3) forma de ejecución, (4) resultado y (5) estadísticas. MUST mostrar en qué paso se está, permitir volver a un paso anterior sin perder lo cargado y habilitar "Siguiente" solo cuando los datos del paso son válidos. Mientras se genera el mosaico, el stepper MUST indicarlo en la posición del paso 4.

#### Scenario: Paso incompleto
- **WHEN** en el paso 1 se cargó el lote pero no la imagen objetivo
- **THEN** "Siguiente" queda deshabilitado con el mensaje "falta la imagen objetivo"

#### Scenario: Volver atrás
- **WHEN** en el paso 3 se vuelve al paso 2 y se cambian las columnas
- **THEN** el lote y el objetivo siguen cargados y al avanzar se conserva la forma de ejecución elegida

#### Scenario: Generando
- **WHEN** se aprieta "Generar mosaico" en el paso 3
- **THEN** el stepper marca el paso 4 como actual con el nombre "Generando" hasta que el trabajo termina

### Requirement: Pantalla única guiada por el stepper
La interfaz MUST ser una única pantalla cuya navegación es solo el stepper y los botones de cada paso: MUST NOT tener barra lateral (sidebar), menú de navegación global ni otras secciones a las que saltar. El stepper MUST quedar visible arriba en todos los pasos, y la ejecución, el resultado y las estadísticas MUST mostrarse en la misma pantalla, como pasos del stepper.

#### Scenario: Navegación
- **WHEN** se abre la aplicación en un navegador de escritorio
- **THEN** solo se ven el stepper y el contenido del paso actual, sin sidebar ni menú global

#### Scenario: Pantalla angosta
- **WHEN** la ventana mide 400 px de ancho
- **THEN** el stepper se compacta (por ejemplo "Paso 2 de 5 · Parámetros") y no aparece ningún menú lateral ni hamburguesa

### Requirement: Estadísticas a pedido
La pantalla de resultado MUST tener un botón "Ver estadísticas" que avance al paso 5, donde se muestra la tabla de tiempos: carga común (indicando si se reutilizó), preparación de teselas, descriptores del objetivo, matching + top-k, composición, transferencias host→device (copia a staging y DMA), transferencias device→host, total del backend e inicialización del backend. Las filas que no aplican MUST mostrarse como "no aplica". Las estadísticas MUST NOT mostrarse en la pantalla de resultado.

#### Scenario: Trabajo en CPU
- **WHEN** termina un trabajo en CPU y se aprieta "Ver estadísticas"
- **THEN** se pasa al paso 5, las filas de transferencias dicen "no aplica" y el resto tiene tiempos en ms

#### Scenario: Resultado sin estadísticas
- **WHEN** se muestra la pantalla de resultado
- **THEN** no hay ninguna tabla ni gráfico de tiempos debajo del mosaico

#### Scenario: Trabajo fallido
- **WHEN** el trabajo falló
- **THEN** la pantalla de resultado muestra el motivo y no ofrece "Ver estadísticas"

## ADDED Requirements

### Requirement: Navegación entre pasos en ambos sentidos
Cada paso MUST ofrecer "Atrás" hacia el paso anterior, si existe, y una acción para ir al siguiente, si es alcanzable. El stepper MUST permitir saltar a cualquier paso alcanzable, anterior o posterior. Los pasos 4 y 5 MUST ser alcanzables solo si hay un resultado de esta pestaña (el paso 5, solo si el trabajo terminó bien). Mientras se genera el mosaico no se MUST poder navegar.

#### Scenario: Del resultado a la ejecución
- **WHEN** en el paso 4 se aprieta "Atrás"
- **THEN** se vuelve al paso 3 con la forma de ejecución elegida

#### Scenario: De la ejecución al último resultado
- **WHEN** hay un resultado de esta pestaña y en el paso 3 se aprieta "Ver resultado"
- **THEN** se pasa al paso 4 con el mismo mosaico, sin lanzar otro trabajo

#### Scenario: Salto hacia adelante desde el stepper
- **WHEN** hay un resultado y desde el paso 1 se elige "5. Estadísticas" en el stepper
- **THEN** se muestran las estadísticas de ese resultado

#### Scenario: Sin resultado
- **WHEN** todavía no se generó ningún mosaico en esta pestaña
- **THEN** los pasos 4 y 5 del stepper no son links y el paso 3 no ofrece "Ver resultado"

### Requirement: Resultado sin scroll
La pantalla de resultado MUST entrar en el alto de la ventana debajo del stepper, con el visor del mosaico ocupando el espacio que dejan el título y las acciones, para que la rueda del mouse se use solo para el zoom y ninguna acción quede fuera de la vista.

#### Scenario: Ventana de escritorio
- **WHEN** se muestra el resultado en una ventana de 1440 × 900 px
- **THEN** la página no tiene scroll vertical y se ven el mosaico, la descarga, "Atrás", "Ver estadísticas" y "Volver a empezar"

### Requirement: Estadísticas con scroll
El paso de estadísticas MUST permitir scrollear la página cuando su contenido (banda de verificación, gráfico y tablas) supera el alto de la ventana, y MUST ofrecer "Atrás" hacia el resultado y "Volver a empezar".

#### Scenario: Comparación en una ventana baja
- **WHEN** se muestran las estadísticas de una ejecución con "Ambas" en una ventana de 700 px de alto
- **THEN** la página scrollea hasta la tabla de tiempos y al final están "Atrás" y "Volver a empezar"
