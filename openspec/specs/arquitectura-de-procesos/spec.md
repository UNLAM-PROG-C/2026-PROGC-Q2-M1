# arquitectura-de-procesos Specification

## Purpose

Organiza la aplicación en un frontend independiente y un backend formado por un proceso web, un proceso worker y un pool de decodificación, de modo que la interfaz siga respondiendo durante el cómputo, los contextos de GPU tengan un único dueño y entre procesos viajen solo datos livianos.

## Requirements
### Requirement: Frontend desacoplado del backend
El frontend MUST ser una aplicación independiente, en su propia carpeta y con su propio servidor, que se comunica con el backend solo por la API HTTP y el WebSocket. El backend MUST NOT servir los archivos de la interfaz ni depender del código del frontend.

#### Scenario: Backend sin frontend
- **WHEN** se levanta solo el backend
- **THEN** la API y el WebSocket funcionan y se pueden probar con un cliente HTTP, sin ningún archivo del frontend

### Requirement: Proceso web sin cómputo pesado
El proceso web del backend MUST limitarse a recibir y guardar subidas, validar parámetros, enviar órdenes al worker, reenviar eventos al navegador y servir resultados y archivos subidos. MUST NOT decodificar imágenes, ejecutar backends ni crear contextos de GPU.

#### Scenario: Interfaz durante un trabajo largo
- **WHEN** hay un trabajo en CPU en curso
- **THEN** el backend responde a `GET /api/state` sin demoras atribuibles al trabajo y la interfaz sigue respondiendo

### Requirement: Worker dueño de los contextos de GPU
Un único proceso worker MUST crear, usar y liberar todos los contextos CUDA/OpenCL. Al iniciar MUST detectar y precalentar todos los backends disponibles y publicar su estado antes de aceptar trabajos.

#### Scenario: Arranque
- **WHEN** se inicia la aplicación
- **THEN** el worker publica el estado de todos los backends con sus tiempos de inicialización, y recién entonces la interfaz habilita la ejecución

### Requirement: Procesos creados con spawn
Todos los procesos hijos (worker y pool de decodificación) MUST crearse con el método `spawn`, en todas las plataformas.

#### Scenario: Pool creado después del contexto CUDA
- **WHEN** el worker ya tiene un contexto CUDA y crea el pool de decodificación
- **THEN** los procesos del pool arrancan sin heredar el contexto y la carga funciona

### Requirement: Mensajes livianos entre procesos
Por las colas entre web y worker MUST viajar solo identificadores, rutas, parámetros, mensajes de progreso, estados, tiempos y resultados de verificación. MUST NOT viajar arrays de imágenes; los resultados se escriben a disco en el directorio del trabajo y se informan por ruta.

#### Scenario: Resultado de un trabajo
- **WHEN** termina un trabajo
- **THEN** el worker guarda la imagen en el directorio del trabajo y envía a la web solo su ruta, sus dimensiones y los tiempos

### Requirement: Un trabajo a la vez
El sistema MUST ejecutar como máximo un trabajo por vez. Si llega una orden mientras hay un trabajo en curso, el proceso web MUST rechazarla con un código de conflicto, y el worker MUST rechazarla también si llegara a recibirla.

#### Scenario: Segundo trabajo en paralelo
- **WHEN** hay un trabajo en curso y se envía `POST /api/jobs`
- **THEN** la respuesta es 409 con el mensaje "ya hay un trabajo en curso"

### Requirement: Fallas del worker visibles
Si el worker termina inesperadamente, el proceso web MUST detectarlo, marcar el trabajo en curso como fallido, informar el estado a la interfaz y relanzar el worker.

#### Scenario: Worker abortado
- **WHEN** el proceso worker muere durante un trabajo
- **THEN** la interfaz muestra "el worker se detuvo inesperadamente", el trabajo queda fallido y, tras relanzarse el worker, se puede ejecutar otro trabajo

### Requirement: Apagado ordenado
Al detener la aplicación, el proceso web MUST pedir al worker que termine; el worker MUST cerrar el pool, liberar los contextos de GPU y salir dentro de un tiempo límite configurado, pasado el cual se lo termina forzosamente.

#### Scenario: Ctrl+C
- **WHEN** se detiene la aplicación con Ctrl+C sin trabajos en curso
- **THEN** el worker libera los contextos y el frontend, el proceso web y el worker terminan sin dejar procesos huérfanos
