# TP1 - Parte 1 - Ejercicio 1: Arbol de procesos (Java + Maven)

Implementacion en Java del arbol de procesos pedido en el TP1 - Parte 1. Cada letra del
arbol es un **proceso del sistema operativo** distinto (una JVM propia), creado con
`ProcessBuilder`. Los hijos de un mismo nodo se lanzan de forma **concurrente**: primero se
crean todos con `start()` y recien despues se espera a cada uno con `waitFor()`.

El mismo codigo esta explicado paso a paso en el cuaderno
[`TP1_Ejercicio1_ArbolProcesos_M1.ipynb`](TP1_Ejercicio1_ArbolProcesos_M1.ipynb) (version
Colab, entregada por MIeL). Este proyecto Maven es la version compilable del mismo ejercicio.

## Arbol que se construye

```
A
└── B
    ├── C
    │   └── E
    │       ├── H
    │       └── I
    └── D
        ├── F
        └── G
```

- `A` es la raiz (clase `Main`).
- `B`, `C`, `D` y `E` son nodos intermedios: crean a sus hijos y los esperan.
- `F`, `G`, `H` e `I` son hojas: no crean a nadie.

Todos los nodos, apenas arrancan, imprimen su nombre, su **PID** y el **PPID** de su padre
(via `ProcessHandle.current()`), y se mantienen vivos 10 segundos para que el arbol completo
pueda verse con `pstree` antes de que empiecen a terminar.

## Requisitos

| Herramienta | Version minima | Como verificar |
| ----------- | -------------- | -------------- |
| JDK         | 17             | `java -version` |
| Apache Maven| 3.8            | `mvn -v` |

> Se usa Java 17 porque `ProcessHandle` (PID / PPID) requiere Java 9 o superior, y 17 es la
> LTS que compila el proyecto (`maven.compiler.release=17`).

## Como buildear

Parado en esta carpeta (`TP1-parte1/03_Java`, donde esta el `pom.xml`):

```bash
mvn clean package
```

Eso compila las cuatro clases y genera el jar ejecutable `target/arbol-procesos.jar`.

## Como ejecutar

Cualquiera de las dos formas sirve:

```bash
# 1) Con el jar ya empaquetado
java -jar target/arbol-procesos.jar
```

```bash
# 2) Directo desde Maven, sin empaquetar
mvn exec:java
```

Los procesos hijos se lanzan reutilizando el mismo `java` y el mismo classpath del proceso
padre, asi que funciona igual en las dos modalidades y en Linux, macOS y Windows.

El programa tarda un poco mas de 20 segundos en terminar: cada proceso vive 10 segundos y la
raiz espera a que todo el subarbol termine antes de irse.

### Salida esperada

Nueve lineas, una por proceso (los PID cambian en cada corrida; el orden entre hermanos puede
variar, justamente porque se crean de forma concurrente):

```
Proceso A | PID: 25144 | PPID: 28844
Proceso B | PID: 19860 | PPID: 25144
Proceso C | PID: 34920 | PPID: 19860
Proceso D | PID: 16712 | PPID: 19860
Proceso E | PID: 24256 | PPID: 34920
Proceso F | PID: 26264 | PPID: 16712
Proceso G | PID: 33380 | PPID: 16712
Proceso H | PID: 21284 | PPID: 24256
Proceso I | PID: 17072 | PPID: 24256
```

Se verifica que el PPID de cada nodo coincide con el PID del padre que le corresponde en el
arbol de arriba.

### Ver el arbol real de procesos

**Linux / macOS / Colab** - dejar corriendo el programa en segundo plano y mirarlo con
`pstree` mientras vive:

```bash
java -jar target/arbol-procesos.jar > salidaJava 2>&1 &
sleep 5
pstree -pT $(pgrep -f arbol-procesos.jar | head -1)
```

```
java(16551)───java(16575)─┬─java(16599)───java(16647)─┬─java(16719)
                          │                           └─java(16724)
                          └─java(16602)─┬─java(16666)
                                        └─java(16669)
```

**Windows (PowerShell)** - no hay `pstree`, pero se puede listar PID/PPID de las JVM vivas:

```powershell
Get-CimInstance Win32_Process -Filter "Name='java.exe'" |
  Select-Object ProcessId, ParentProcessId, CommandLine
```

## Estructura del proyecto

```
03_Java/
├── pom.xml                                   # build Maven (jar ejecutable + exec:java)
├── README.md
├── TP1_Ejercicio1_ArbolProcesos_M1.ipynb     # cuaderno Colab entregado por MIeL
└── src/main/java/arbolprocesos/
    ├── Main.java              # Proceso A (raiz): crea a B y lo espera
    ├── ChildProcess.java      # Cualquier otro nodo; recibe su nombre por args[0]
    ├── ProcessLauncher.java   # Crea los hijos (todos los start(), despues los waitFor())
    └── ProcessInfo.java       # PID / PPID del proceso actual y tiempo de vida
```

## Limpieza

```bash
mvn clean
```
