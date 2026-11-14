# carga-de-imagenes Specification

## Purpose

Convierte el lote de teselas y la imagen objetivo subidos por el usuario en arrays normalizados (`tiles_src` y `target_src`) que reciben todos los backends. Es la etapa común: no forma parte de la comparación, pero se mide y se informa por separado.

## Requirements
### Requirement: Normalización de teselas
El sistema MUST convertir cada imagen del lote en una tesela de 128×128 píxeles RGB de 8 bits: decodificar, aplicar la orientación EXIF, convertir a RGB (descartando alfa y expandiendo escala de grises), recortar el cuadrado central y redimensionar a 128×128. El resultado del lote MUST ser un array `tiles_src` de forma `[N, 128, 128, 3]` y tipo uint8.

#### Scenario: Imagen apaisada
- **WHEN** el lote contiene una imagen de 400×200 píxeles
- **THEN** se toma el cuadrado central de 200×200 (columnas 100 a 299) y se redimensiona a 128×128

#### Scenario: Orientación EXIF
- **WHEN** una imagen JPEG tiene la etiqueta EXIF de orientación 6 (rotada 90°)
- **THEN** la tesela resultante se ve con la orientación correcta, igual que la mostraría un visor de imágenes

#### Scenario: Imagen con canal alfa o en escala de grises
- **WHEN** el lote contiene un PNG RGBA y un PNG en escala de grises
- **THEN** ambas teselas quedan con 3 canales RGB

### Requirement: Formatos admitidos y archivos inválidos
El sistema MUST aceptar imágenes JPEG, PNG y WebP. Los archivos que no se puedan decodificar MUST omitirse del lote, y el sistema MUST informar cuántos y cuáles se omitieron. Si no queda ninguna tesela válida, el trabajo MUST fallar con un mensaje claro.

#### Scenario: Un archivo corrupto en el lote
- **WHEN** el lote tiene 10 archivos y uno está corrupto
- **THEN** `tiles_src` tiene N = 9 teselas y se informa el nombre del archivo omitido

#### Scenario: Lote sin teselas válidas
- **WHEN** ningún archivo del lote se puede decodificar
- **THEN** el trabajo termina con error "no hay teselas válidas" y no se ejecuta ningún backend

### Requirement: Orden determinista de las teselas
El índice de cada tesela MUST corresponder a su posición en el orden lexicográfico de las rutas relativas de los archivos del lote, después de omitir los inválidos. El orden MUST ser independiente de la cantidad de procesos de decodificación y del orden en que terminen.

#### Scenario: Misma subida, distinto paralelismo
- **WHEN** el mismo lote se carga con 1 proceso de decodificación y con 8
- **THEN** los dos `tiles_src` son idénticos byte a byte

### Requirement: Decodificación en paralelo
La decodificación de teselas MUST ejecutarse en un pool de procesos que escriba cada tesela directamente en su posición de un array compartido preasignado de forma `[N, 128, 128, 3]`, sin enviar los píxeles por colas entre procesos.

#### Scenario: Lote grande
- **WHEN** se cargan 1.000 teselas en una máquina con 8 núcleos
- **THEN** la decodificación usa varios procesos y el array resultante se obtiene sin serializar imágenes entre ellos

### Requirement: Preparación de la imagen objetivo
El sistema MUST decodificar la imagen objetivo, aplicar la orientación EXIF y convertirla a RGB. A partir de `cols`, MUST derivar `rows = max(1, round(cols · alto / ancho))` y redimensionar la imagen a exactamente `cols·8` píxeles de ancho por `rows·8` de alto. El resultado MUST ser `target_src` de forma `[rows·8, cols·8, 3]` y tipo uint8.

#### Scenario: Objetivo 4:3
- **WHEN** la imagen objetivo mide 4000×3000 y `cols = 100`
- **THEN** `rows = 75` y `target_src` tiene forma `[600, 800, 3]`

#### Scenario: Objetivo muy apaisado
- **WHEN** la imagen objetivo mide 3000×10 y `cols = 10`
- **THEN** `rows = 1` (nunca 0)

### Requirement: Medición y reutilización de la carga
El tiempo de la etapa común de carga MUST medirse e informarse separado del tiempo de los backends. Si se ejecuta otra vez con el mismo lote (y, para el objetivo, la misma imagen y el mismo `cols`), el sistema MUST reutilizar los arrays ya cargados en lugar de decodificar de nuevo, e informar que la carga se reutilizó.

#### Scenario: Mismo trabajo con dos backends
- **WHEN** se ejecuta un trabajo con CPU y luego el mismo lote y objetivo con CUDA
- **THEN** la segunda ejecución no vuelve a decodificar y reporta la carga como reutilizada

#### Scenario: Cambia la cantidad de columnas
- **WHEN** se repite un trabajo con el mismo lote pero con otro `cols`
- **THEN** se reutilizan las teselas y solo se vuelve a preparar la imagen objetivo

