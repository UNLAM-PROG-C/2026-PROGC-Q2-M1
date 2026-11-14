# deteccion-de-backends Specification

## Purpose

Determina qué backends puede usar la máquina, informa el estado de cada uno con su dispositivo o el motivo de indisponibilidad, y resuelve qué backend ejecuta un trabajo según la elección del usuario.

## Requirements
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

### Requirement: Selección respetando lo pedido
Si se pide un backend (por nombre, como hace el benchmark, o como resultado de la forma de ejecución elegida en la interfaz), el trabajo MUST ejecutarse con ese backend, aunque haya otro más rápido disponible. Si se pide un backend no disponible, el trabajo MUST rechazarse indicando el motivo, sin sustituirlo por otro.

#### Scenario: CPU elegida con GPU disponible
- **WHEN** CUDA está disponible y se pide CPU secuencial
- **THEN** el trabajo se ejecuta con CPU secuencial

#### Scenario: Backend pedido no disponible
- **WHEN** se pide OpenCL y OpenCL no está disponible
- **THEN** el trabajo se rechaza con el motivo de indisponibilidad de OpenCL

### Requirement: Selección automática de la GPU
El sistema MUST determinar una única GPU preferida para la opción "GPU" de la interfaz, según la placa disponible: CUDA si está disponible (placa NVIDIA), si no OpenCL, si no ninguna. Cuando no hay GPU preferida, MUST informar un motivo que combine los de CUDA y OpenCL. La GPU preferida MUST NOT ser nunca CPU secuencial.

#### Scenario: Placa NVIDIA con CUDA y OpenCL
- **WHEN** CUDA y OpenCL están disponibles sobre una GeForce RTX 3060
- **THEN** la GPU preferida es CUDA con dispositivo "GeForce RTX 3060"

#### Scenario: Solo OpenCL
- **WHEN** CUDA no está disponible y OpenCL sí
- **THEN** la GPU preferida es OpenCL con el nombre de su dispositivo

#### Scenario: Sin GPU
- **WHEN** ni CUDA ni OpenCL están disponibles
- **THEN** no hay GPU preferida y el motivo informado indica que no se detectó una GPU compatible

