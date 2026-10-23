# Spec Delta

## Purpose

Implementación secuencial de referencia del algoritmo de fotomosaico: siempre disponible, sin dependencias de GPU, y escrita para explicar la correspondencia "un hilo de GPU = una iteración del bucle".

## ADDED Requirements

### Requirement: Disponibilidad incondicional
El backend CPU secuencial MUST estar disponible en toda instalación, incluso si no hay GPU ni están instaladas las dependencias de CUDA u OpenCL, y MUST poder elegirse aunque haya una GPU disponible.

#### Scenario: Instalación solo CPU
- **WHEN** la aplicación se instala solo con las dependencias base
- **THEN** el backend CPU secuencial se inicializa y ejecuta trabajos

### Requirement: Ejecución estrictamente secuencial
Todas las etapas comparadas MUST ejecutarse en un único hilo y sin vectorización SIMD automática: sin paralelismo del compilador JIT, sin operaciones vectorizadas de NumPy sobre todos los pares celda-tesela y sin BLAS. Las etapas comparadas MUST NOT implementarse con bucles en Python interpretado: deben ser código compilado.

#### Scenario: Ejecución de un trabajo grande
- **WHEN** se ejecuta un trabajo con N = 1.000 y M = 10.000
- **THEN** durante las etapas comparadas el proceso usa un solo núcleo de CPU

#### Scenario: Configuración del compilador
- **WHEN** se inicializa el backend
- **THEN** la vectorización automática de bucles del compilador JIT está desactivada y se puede verificar por configuración

### Requirement: Correspondencia con los kernels de GPU
Cada etapa MUST implementarse con bucles explícitos cuya iteración más interna sobre los elementos de salida corresponda al trabajo de un hilo del kernel equivalente, documentada en comentarios que nombren el kernel correspondiente.

#### Scenario: Lectura del código de composición
- **WHEN** se lee la función de composición del backend CPU
- **THEN** un comentario indica que cada iteración sobre píxeles de salida equivale a un hilo del kernel `compose`

### Requirement: Top-k secuencial con arreglo ordenado
El top-k de cada celda MUST obtenerse recorriendo las N teselas una vez y manteniendo un arreglo ordenado de tamaño `k` con inserción, aplicando el criterio (distancia, índice) del algoritmo.

#### Scenario: Inserción en el medio
- **WHEN** el arreglo de una celda con `k = 3` tiene distancias [1, 4, 9] y aparece una tesela a distancia 2
- **THEN** el arreglo queda [1, 2, 4]

### Requirement: Medición con reloj de alta resolución
Los tiempos por etapa y el total del backend CPU MUST medirse con un reloj monotónico de alta resolución, tomando cada medición al terminar efectivamente la etapa.

#### Scenario: Tiempos consistentes
- **WHEN** termina un trabajo con el backend CPU
- **THEN** la suma de los tiempos por etapa es menor o igual al total informado

### Requirement: Memoria acotada en el matching
El backend CPU MUST procesar el matching por bloques de celdas cuyo tamaño se derive de un presupuesto de memoria configurado, de modo que la matriz parcial de distancias no supere ese presupuesto.

#### Scenario: Problema grande
- **WHEN** N = 5.000 y M = 40.000
- **THEN** la memoria usada por la matriz parcial de distancias no supera el presupuesto configurado
