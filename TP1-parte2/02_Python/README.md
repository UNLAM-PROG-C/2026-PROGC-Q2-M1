# TP1 - Parte 2 - Ejercicio 2: Combates Eternos en el Netherrealm (Python + Make)

Implementacion en Python de la simulacion masiva de torneos de Mortal Kombat pedida en el
TP1 - Parte 2. Cada trabajador es un **hilo** (`threading.Thread`) que simula su propia
porcion de los torneos totales, y entre ellos **no se usa ningun mecanismo de comunicacion ni
de sincronizacion** (nada de `Lock`, `Semaphore`, `Event` ni colas). Los N hilos se crean de
forma **concurrente**: primero se lanzan todos en un bucle y recien despues se espera a cada
uno con `join()` en otro bucle.

El mismo codigo esta explicado paso a paso en el cuaderno
[`TP1_Parte2_Ejercicio2_MortalKombat_M1.ipynb`](TP1_Parte2_Ejercicio2_MortalKombat_M1.ipynb)
(version Colab, entregada por MIeL). Este proyecto con `Makefile` es la version buildeable y
ejecutable del mismo ejercicio: `src/mortal_kombat.py` es identico al archivo que el cuaderno
genera con `%%writefile`.

## Que simula cada hilo

Cada hilo corre `TORNEOS / HILOS` torneos completos e independientes. Un torneo es:

| Etapa | Detalle |
| ----- | ------- |
| Sorteo | 8 de los 12 luchadores disponibles, con la misma probabilidad para todos |
| Cuadro | Eliminacion simple: Cuartos de final (4 combates) -> Semifinal (2) -> Final (1) |
| Combate | Por turnos; ataca primero el de mayor velocidad (si empatan, se sortea) |
| Ataque | El defensor puede bloquear (dano 0); si no, dano = `ataque - defensa` (minimo 1), duplicado si es golpe critico |
| Fin del combate | Cuando un luchador queda con vida <= 0; el otro pasa de ronda |

Los 12 luchadores tienen atributos **fijos** (dentro de los rangos de la consigna) para que
las distintas corridas sean comparables entre si. Cada hilo acumula sus propios contadores:
turnos simulados, victorias por luchador y campeonatos por luchador. El hilo principal los
suma **despues** de los `join()`.

### Como se evita la sincronizacion

- Antes de crear ningun hilo, el hilo principal genera **una semilla por hilo** de forma
  secuencial. Cada hilo usa su propio `random.Random(seed)`, asi que no comparte el generador
  aleatorio con nadie (el `random` global de Python si es compartido, y usarlo desde varios
  hilos seria justamente el estado compartido que la consigna prohibe).
- La lista de resultados se reserva con su tamano final **antes** de lanzar los hilos, y cada
  hilo escribe unicamente en su propio diccionario. Como dos hilos nunca escriben la misma
  posicion, no hace falta ningun lock.
- La unica lectura de los resultados ocurre en el hilo principal **despues** de los `join()`,
  que ya garantizan que todos los hilos terminaron de escribir.
- El reparto de torneos es parejo: si el total no es multiplo de la cantidad de hilos, los
  primeros hilos toman un torneo extra cada uno (nadie queda sin trabajo ni se pisan).

## Requisitos

| Herramienta | Version minima | Como verificar |
| ----------- | -------------- | -------------- |
| Python 3 | 3.8 | `python3 --version` (en Windows, `python --version`) |
| GNU Make | 3.8 (opcional) | `make --version` |
| matplotlib | 3.5 (opcional) | solo para el grafico del cuaderno |

El programa usa **solo la biblioteca estandar** (`threading`, `random`, `time`,
`collections`): no hay que instalar nada para buildearlo ni ejecutarlo. `requirements.txt`
existe unicamente para reproducir el grafico de tiempo vs. hilos del cuaderno
(`make deps`, o `pip install -r requirements.txt`).

`make` es opcional: debajo de cada target esta el equivalente invocando `python` directo,
para Windows, donde `make` no viene instalado.

## Como buildear

Python es interpretado, asi que "buildear" es compilarlo a bytecode, lo que ademas valida que
el archivo no tenga errores de sintaxis. Parado en esta carpeta (`TP1-parte2/02_Python`,
donde esta el `Makefile`):

```bash
make build
```

Equivalente sin `make`:

```bash
python3 -m compileall -q src/mortal_kombat.py    # Linux / macOS / Colab
python -m compileall -q src/mortal_kombat.py     # Windows
```

Eso deja el bytecode en `src/__pycache__/`. Si no imprime nada, compilo bien.

## Como ejecutar

```bash
# Valores por defecto del Makefile: 10000 torneos, 4 hilos
make run
```

```bash
# Cambiando la cantidad de torneos y de hilos
make run TORNEOS=100000 HILOS=8
```

Equivalente sin `make`:

```bash
python3 src/mortal_kombat.py 100000 8     # Linux / macOS / Colab
python src/mortal_kombat.py 100000 8      # Windows (cmd o PowerShell)
```

Los dos argumentos de linea de comandos son:

| Parametro | Posicion | Default | Significado |
| --------- | -------- | ------- | ----------- |
| Torneos | `sys.argv[1]` | 10000 | Cantidad total de torneos a simular entre todos los hilos |
| Hilos | `sys.argv[2]` | 4 | Cantidad de hilos trabajadores a crear |

Si alguno de los dos no es un entero positivo, el programa avisa y termina con codigo de
salida 1.

### Salida esperada

Los numeros cambian en cada corrida, porque las semillas se generan al azar:

```
$ make run TORNEOS=5000 HILOS=4
Torneos simulados: 5000
Hilos usados: 4
Turnos de combate totales: 454967
Victorias por luchador:
  Liu Kang: 3103
  Kung Lao: 670
  Johnny Cage: 1658
  Reptile: 1176
  Sub-Zero: 3245
  Shang Tsung: 686
  Kitana: 921
  Jax: 7609
  Mileena: 1068
  Baraka: 8291
  Scorpion: 3581
  Raiden: 2992
Campeonatos por luchador:
  Liu Kang: 150
  Kung Lao: 0
  Johnny Cage: 34
  Reptile: 3
  Sub-Zero: 148
  Shang Tsung: 1
  Kitana: 2
  Jax: 1873
  Mileena: 14
  Baraka: 2351
  Scorpion: 286
  Raiden: 138
Tiempo total: 99.9 ms
```

Los mas ganadores son siempre Jax y Baraka: son los que tienen mas vida y mas ataque, asi que
el ranking depende de los atributos fijos y no del azar de la corrida.

### Medir el tiempo segun la cantidad de hilos

El programa imprime el tiempo total (reloj de pared) de cada corrida, y el `Makefile` trae un
target que repite la medicion variando la cantidad de hilos con los torneos fijos:

```bash
make bench
make bench BENCH_TORNEOS=50000 BENCH_HILOS="1 2 4 8 16 32"
```

Equivalente sin `make`:

```bash
for n in 1 2 4 8 16; do python3 src/mortal_kombat.py 20000 $n | tail -1; done
```

El cuaderno automatiza esa medicion (varias repeticiones por cada cantidad) y grafica el
promedio con `matplotlib`. **Conclusion:** aumentar la cantidad de hilos **no** baja el
tiempo total. En CPython existe el GIL (Global Interpreter Lock), que permite que un solo
hilo ejecute bytecode Python a la vez sin importar cuantos nucleos haya; como simular
combates es trabajo puro de CPU, los hilos se turnan en vez de correr en paralelo. Por eso el
tiempo queda mas o menos plano y, con muchos hilos, hasta empeora un poco por el overhead de
crearlos y de los cambios de contexto. Es la diferencia principal con el
[Ejercicio 1 en C++](../01_C++/README.md), donde `std::thread` si corre en paralelo real
sobre varios nucleos y el tiempo baja hasta agotarlos. Una corrida de ejemplo con 20000
torneos:

```
hilos=1 -> Tiempo total: 388.6 ms
hilos=2 -> Tiempo total: 410.7 ms
hilos=4 -> Tiempo total: 420.4 ms
hilos=8 -> Tiempo total: 395.4 ms
```

## Estructura del proyecto

```
02_Python/
├── Makefile                                       # build (compileall) + run/bench con TORNEOS y HILOS
├── README.md
├── requirements.txt                               # solo matplotlib, para el grafico del cuaderno
├── TP1_Parte2_Ejercicio2_MortalKombat_M1.ipynb    # cuaderno Colab entregado por MIeL
└── src/
    └── mortal_kombat.py                           # worker (cuerpo del hilo), simulate_tournament, simulate_combat y main
```

## Limpieza

```bash
make clean
```

Borra el bytecode generado (`src/__pycache__`). Equivalente sin `make`:
`rm -rf src/__pycache__` (o `rmdir /s /q src\__pycache__` en Windows).
