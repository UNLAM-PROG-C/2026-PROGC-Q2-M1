# TP1 - Parte 2 - Ejercicio 1: El entrenamiento de Naruto Uzumaki (C++ + Make)

Implementacion en C++ del Jutsu Multi Clones de Sombra pedido en el TP1 - Parte 2. Cada clon
es un **hilo real** del sistema operativo (`std::thread`), y entre ellos **no se usa ningun
mecanismo de comunicacion ni de sincronizacion** (nada de `mutex`, `condition_variable`,
`atomic` ni colas). Los N clones se crean de forma **concurrente**: primero se lanzan todos
en un bucle y recien despues se espera a cada uno con `join()` en otro bucle.

El mismo codigo esta explicado paso a paso en el cuaderno
[`TP1_Parte2_Ejercicio1_Naruto_M1.ipynb`](TP1_Parte2_Ejercicio1_Naruto_M1.ipynb) (version
Colab, entregada por MIeL). Este proyecto con `Makefile` es la version buildeable y
ejecutable del mismo ejercicio: `src/naruto_training.cpp` es identico al archivo que el
cuaderno genera con `%%writefile`.

## Que hace cada clon

| Parametro | Valor |
| --------- | ----- |
| Chakra inicial | aleatorio entre 5 y 10 unidades |
| Costo de un intento | 1 unidad de Chakra |
| Duracion de un intento | aleatoria entre 100 y 200 ms |
| Probabilidad de subir un nivel | 50% por intento |
| Fin del clon | al quedarse sin Chakra el hilo termina (el clon desaparece) |

Al final, Naruto incorpora como propio el nivel alcanzado por todos los clones: el hilo
principal **suma** los niveles individuales despues de los `join()`.

### Como se evita la sincronizacion

- Antes de crear ningun hilo, el hilo principal genera **una semilla por clon** de forma
  secuencial. Cada clon usa su propio `std::mt19937`, asi que no comparte el generador
  aleatorio con nadie (un generador global compartido si necesitaria un lock).
- El vector de resultados (`levels`) se reserva con su tamano final **antes** de lanzar los
  hilos, y cada clon escribe unicamente su propia posicion. Como dos hilos nunca escriben la
  misma posicion ni el vector se redimensiona, no hace falta ningun lock.
- La unica lectura de los resultados ocurre en el hilo principal **despues** de los `join()`,
  que ya garantizan que todos los clones terminaron de escribir.

## Requisitos

| Herramienta | Version minima | Como verificar |
| ----------- | -------------- | -------------- |
| Compilador C++ con soporte C++17 (g++ o clang++) | g++ 7 / clang++ 5 | `g++ --version` |
| GNU Make | 3.8 (opcional) | `make --version` |

No hay dependencias externas: se usa solo la biblioteca estandar (`<thread>`, `<random>`,
`<chrono>`, `<vector>`).

`make` es opcional: mas abajo esta el equivalente invocando `g++` directo, para Windows,
donde `make` no viene instalado.

## Como buildear

Parado en esta carpeta (`TP1-parte2/01_C++`, donde esta el `Makefile`):

```bash
make build
```

Eso compila `src/naruto_training.cpp` y genera el ejecutable `naruto_training`
(`naruto_training.exe` en Windows).

Equivalente sin `make`:

```bash
g++ -std=c++17 -O2 -Wall -Wextra -pthread -o naruto_training src/naruto_training.cpp
```

> `-pthread` es obligatorio: sin esa flag `std::thread` compila igual pero el programa aborta
> al arrancar en varias distribuciones de Linux (incluida la de Colab).

## Como ejecutar

```bash
# Valor por defecto del Makefile: 10 clones
make run
```

```bash
# Cambiando la cantidad de clones
make run CLONES=20
```

Equivalente sin `make`:

```bash
./naruto_training 10        # Linux / macOS / Colab / Git Bash
naruto_training.exe 10      # Windows (cmd o PowerShell)
```

La cantidad de clones es el unico argumento de linea de comandos:

| Parametro | Posicion | Default | Significado |
| --------- | -------- | ------- | ----------- |
| Clones    | `argv[1]` | 10 | Cantidad de clones de sombra, es decir, de hilos a crear |

Si se pasa un valor que no sea un entero positivo, el programa avisa por `stderr` y termina
con codigo de salida 1.

El programa tarda entre 0,5 y 2 segundos aproximadamente: cada clon hace entre 5 y 10
intentos de 100 a 200 ms, y todos entrenan en paralelo, asi que el total lo marca el clon mas
lento (no la suma de todos).

### Salida esperada

Los niveles cambian en cada corrida, porque tanto el Chakra inicial como el exito de cada
intento son aleatorios:

```
Clon 0: nivel alcanzado = 1
Clon 1: nivel alcanzado = 2
Clon 2: nivel alcanzado = 4
Clon 3: nivel alcanzado = 3
Clon 4: nivel alcanzado = 4
Clon 5: nivel alcanzado = 5
Clon 6: nivel alcanzado = 3
Clon 7: nivel alcanzado = 7
Clon 8: nivel alcanzado = 5
Clon 9: nivel alcanzado = 5
----
Clones: 10
Nivel total ganado por Naruto: 39
Tiempo total: 1647 ms
```

### Medir el tiempo segun la cantidad de clones

El programa imprime el tiempo total (reloj de pared) de cada corrida, asi que se puede
comparar a mano:

```bash
for n in 2 5 10 20 40 80; do make run CLONES=$n | tail -2; done
```

El cuaderno automatiza esa medicion (varias repeticiones por cada cantidad) y grafica el
promedio con `matplotlib`. **Conclusion:** el tiempo total baja mientras la cantidad de
clones es menor o similar a la cantidad de nucleos disponibles; pasado ese punto deja de
bajar y tiende a subir, porque ya no quedan nucleos libres y empieza a pesar el overhead de
crear hilos y de los cambios de contexto. El nivel total de Naruto, en cambio, crece en
promedio proporcionalmente a la cantidad de clones, sin importar cuanto tarde.

### Ver los hilos reales

**Linux / macOS / Colab** - correr el entrenamiento en segundo plano con muchos clones y
contar los hilos del proceso mientras vive:

```bash
./naruto_training 40 > salidaNaruto 2>&1 &
sleep 1
ps -o nlwp= -p $(pgrep -f naruto_training | head -1)   # hilos vivos: 40 clones + el principal
```

**Windows (PowerShell)** - no hay `ps -o nlwp`, pero el contador de hilos esta en el proceso:

```powershell
Start-Process .\naruto_training.exe -ArgumentList 40
(Get-Process naruto_training).Threads.Count
```

## Estructura del proyecto

```
01_C++/
├── Makefile                                     # build (g++) + run con CLONES=N
├── README.md
├── TP1_Parte2_Ejercicio1_Naruto_M1.ipynb        # cuaderno Colab entregado por MIeL
└── src/
    └── naruto_training.cpp                      # trainClone (cuerpo del hilo) y main
```

## Limpieza

```bash
make clean
```

Borra el ejecutable generado. Equivalente sin `make`: `rm -f naruto_training` (o
`del naruto_training.exe` en Windows).
