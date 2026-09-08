# TP1 - Parte 1 - Ejercicio 2: Monitor de Jurassic Park (Python + Make)

Implementacion en Python del monitor de zonas pedido en el TP1 - Parte 1. Cada una de las 5
zonas del parque es vigilada por un **proceso del sistema operativo** distinto, creado con
`multiprocessing.Process` (no `threading.Thread`), coherente con el tema "Procesos Pesados".
Los 5 sistemas de vigilancia se lanzan de forma **concurrente**: primero se crean todos con
`start()` y recien despues se espera a cada uno con `join()`.

El mismo codigo esta explicado paso a paso en el cuaderno
[`TP1_Ejercicio2_JurassicPark_M1.ipynb`](TP1_Ejercicio2_JurassicPark_M1.ipynb) (version
Colab, entregada por MIeL). Este proyecto con `Makefile` es la version buildeable y
ejecutable del mismo ejercicio: `src/jurassic_park_monitor.py` es identico al archivo que el
cuaderno genera con `%%writefile`.

## Zonas y eventos

| Zona | Eventos (probabilidad) |
| ---- | ---------------------- |
| Sector del Tiranosaurio | Todo normal (0.80), **Tiranosaurio fuera del recinto** (0.10), **Falla en el cerco electrico** (0.10) |
| Area de Velociraptores | Todo normal (0.70), Perdida de visibilidad (0.20), **Falla en el cerco electrico** (0.10) |
| Recinto de los Triceratops | Todo normal (0.60), Comportamiento inusual (0.30), Estampida (0.10) |
| Centro de Visitantes | Todo normal (0.80), **Perdida de comunicacion** (0.15), **Alerta de seguridad** (0.05) |
| Laboratorio Genetico | Todo normal (0.80), Falla del sistema (0.10), **Perdida de comunicacion** (0.05), Acceso no autorizado (0.05) |

En **negrita** los eventos considerados **criticos** (dinosaurio fuera de su recinto, falla
en el cerco electrico, perdida de comunicacion y alerta de seguridad). Cada zona, al
terminar, informa su nombre, el total de eventos detectados y cuantos de ellos fueron
criticos.

Cada proceso hijo hace `random.seed()` al arrancar: en Linux/Colab los procesos se crean por
defecto con `fork()`, que copia el estado del generador aleatorio del padre; sin ese reseed
las 5 zonas podrian repetir exactamente la misma secuencia de eventos.

## Requisitos

| Herramienta | Version minima | Como verificar |
| ----------- | -------------- | -------------- |
| Python      | 3.8            | `python3 --version` |
| GNU Make    | 3.8 (opcional) | `make --version` |

No hay dependencias externas: se usa solo la biblioteca estandar (`multiprocessing`,
`random`, `argparse`, `time`, `os`), asi que no hace falta `pip install` ni entorno virtual.

`make` es opcional: mas abajo esta el equivalente ejecutando `python` directo, para Windows,
donde `make` no viene instalado.

## Como buildear

Parado en esta carpeta (`TP1-parte1/02_Python`, donde esta el `Makefile`):

```bash
make build
```

Python no linkea nada, asi que "buildear" aca es compilar a bytecode con
`python3 -m compileall`, que valida la sintaxis y deja los `.pyc` en `src/__pycache__/`.

Equivalente sin `make`:

```bash
python -m compileall -q src
```

## Como ejecutar

```bash
# Valores por defecto del Makefile: 12 segundos de monitoreo, reporte cada 2 segundos
make run
```

```bash
# Cambiando los parametros de duracion y frecuencia
make run DURATION=30 INTERVAL=1
```

Equivalente sin `make` (Windows incluido):

```bash
python src/jurassic_park_monitor.py --duration 12 --interval 2
```

Los dos parametros que pide el enunciado son argumentos de linea de comandos:

| Parametro | Flag | Default del script | Significado |
| --------- | ---- | ------------------ | ----------- |
| Duracion  | `-d`, `--duration` | 15 s | Tiempo total que dura el monitoreo |
| Frecuencia| `-i`, `--interval` | 2 s  | Segundos entre reporte y reporte de cada zona |

El programa tarda aproximadamente `DURATION` segundos: las 5 zonas monitorean en paralelo y
el proceso padre espera a que todas terminen antes de imprimir la linea final.

### Salida esperada

Los PID cambian en cada corrida y el orden entre zonas puede variar, justamente porque los 5
sistemas de vigilancia corren de forma concurrente. Con `--duration 12 --interval 2` cada
zona detecta 6 eventos:

```
[Area de Velociraptores] proceso iniciado (PID=4748)
[Sector del Tiranosaurio] proceso iniciado (PID=4747)
[Recinto de los Triceratops] proceso iniciado (PID=4749)
[Centro de Visitantes] proceso iniciado (PID=4750)
[Laboratorio Genetico] proceso iniciado (PID=4751)
[Sector del Tiranosaurio] - Todo normal
[Area de Velociraptores] - Todo normal
[Recinto de los Triceratops] - Comportamiento inusual
[Laboratorio Genetico] - Todo normal
[Centro de Visitantes] - Todo normal
...
[Sector del Tiranosaurio] - Falla en el cerco electrico
[Sector del Tiranosaurio] >> Monitoreo finalizado | Total de eventos: 6 | Eventos criticos: 2
[Area de Velociraptores] >> Monitoreo finalizado | Total de eventos: 6 | Eventos criticos: 0
[Recinto de los Triceratops] >> Monitoreo finalizado | Total de eventos: 6 | Eventos criticos: 0
[Laboratorio Genetico] >> Monitoreo finalizado | Total de eventos: 6 | Eventos criticos: 0
[Centro de Visitantes] >> Monitoreo finalizado | Total de eventos: 6 | Eventos criticos: 1
Todos los sistemas de vigilancia finalizaron.
```

### Ver los procesos reales

**Linux / macOS / Colab** - dejar corriendo el monitor en segundo plano y mirar el arbol
mientras vive:

```bash
python3 src/jurassic_park_monitor.py --duration 20 --interval 2 > salidaPython 2>&1 &
sleep 3
pstree -pT $(pgrep -f jurassic_park_monitor.py | head -1)
```

Se ven los 5 procesos hijos colgando del proceso padre.

**Windows (PowerShell)** - no hay `pstree`, pero se puede listar PID/PPID de los procesos
Python vivos:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Select-Object ProcessId, ParentProcessId, CommandLine
```

> En Windows y macOS reciente `multiprocessing` usa `spawn` en lugar de `fork`: por eso el
> script protege la creacion de procesos con `if __name__ == "__main__":`. Funciona igual en
> los tres sistemas operativos.

## Estructura del proyecto

```
02_Python/
├── Makefile                                  # build (compileall) + run con parametros
├── README.md
├── TP1_Ejercicio2_JurassicPark_M1.ipynb      # cuaderno Colab entregado por MIeL
└── src/
    └── jurassic_park_monitor.py              # ZONES, monitor_zone (proceso hijo) y main
```

## Limpieza

```bash
make clean
```

Borra `src/__pycache__/`. Equivalente sin `make`: `rm -rf src/__pycache__`.
