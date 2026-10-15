# Spec Delta

## Purpose

Determina qué backends puede usar la máquina, informa el estado de cada uno con su dispositivo o el motivo de indisponibilidad, y resuelve qué backend ejecuta un trabajo según la elección del usuario.

## ADDED Requirements

### Requirement: Detección al inicio
Al iniciar, el sistema MUST determinar la disponibilidad de cada backend: CUDA si su biblioteca se puede importar, el driver inicializa y hay al menos un dispositivo; OpenCL si su biblioteca se puede importar y existe al menos una GPU en alguna plataforma; CPU secuencial siempre.

#### Scenario: Máquina sin bibliotecas de GPU
- **WHEN** no están instaladas las bibliotecas de CUDA ni de OpenCL
- **THEN** CUDA y OpenCL se reportan no disponibles con motivo "biblioteca no instalada" y CPU secuencial disponible

#### Scenario: Driver CUDA sin dispositivos
- **WHEN** la biblioteca CUDA se importa pero el driver informa 0 dispositivos
- **THEN** CUDA se reporta no disponible con motivo "sin dispositivos CUDA"

### Requirement: Estado informable de cada backend
El sistema MUST informar para **todos** los backends, disponibles o no: nombre, si está disponible, nombre del dispositivo cuando lo está, motivo cuando no, tiempo de inicialización y advertencias (por ejemplo, posibles diferencias numéricas).

#### Scenario: Máquina con NVIDIA
- **WHEN** la máquina tiene una GeForce RTX 3060 con CUDA y OpenCL
- **THEN** se informa "CUDA: GeForce RTX 3060", "OpenCL: GeForce RTX 3060" y "CPU secuencial: siempre disponible"

### Requirement: Fallas de inicialización aisladas
Si un backend GPU falla al inicializarse o al precalentarse (driver, contexto o compilación de kernels), el sistema MUST registrar el error completo en el log, marcar ese backend como no disponible con un motivo resumido y continuar con los demás sin terminar.

#### Scenario: Error de compilación de kernels OpenCL
- **WHEN** el compilador OpenCL del driver rechaza `mosaic.cl`
- **THEN** OpenCL queda "no disponible: error de compilación de kernels", el log tiene el build log completo y CUDA y CPU siguen disponibles

### Requirement: Selección respetando al usuario
Si el usuario elige un backend, el trabajo MUST ejecutarse con ese backend, aunque haya otro más rápido disponible. Si elige un backend no disponible, el trabajo MUST rechazarse indicando el motivo, sin sustituirlo por otro.

#### Scenario: CPU elegida con GPU disponible
- **WHEN** CUDA está disponible y el usuario elige CPU secuencial
- **THEN** el trabajo se ejecuta con CPU secuencial

#### Scenario: Backend elegido no disponible
- **WHEN** el usuario elige OpenCL y OpenCL no está disponible
- **THEN** el trabajo se rechaza con el motivo de indisponibilidad de OpenCL

### Requirement: Modo automático
Si el usuario elige "Automático", el sistema MUST usar el primer backend disponible en el orden CUDA, OpenCL, CPU secuencial, e informar cuál usó.

#### Scenario: Solo OpenCL y CPU
- **WHEN** CUDA no está disponible, OpenCL sí, y el usuario elige "Automático"
- **THEN** el trabajo se ejecuta con OpenCL y el resultado indica "OpenCL"
