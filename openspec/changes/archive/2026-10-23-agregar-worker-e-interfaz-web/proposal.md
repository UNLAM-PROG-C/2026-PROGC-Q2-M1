# Proposal

## Why

Los backends y la carga común (cambios 1 y 2) solo se pueden usar desde tests. Para que el TP sirva como demostración hace falta una aplicación local donde una persona suba un lote de teselas y una imagen objetivo, elija los parámetros y la forma de ejecución (CPU o GPU), vea el progreso por etapa y obtenga el mosaico junto con las estadísticas de tiempos. Además, los contextos de GPU y el cómputo pesado tienen que vivir fuera del proceso web para que la interfaz no se bloquee y para respetar las reglas de CUDA sobre procesos.

Es el **cambio 3 de 5**. Depende de los cambios 1 y 2.

## What Changes

- **Backend y frontend desacoplados**, cada uno en su carpeta: `TP-Integrador/backend/` (Python) y `TP-Integrador/frontend/` (React + Vite + TypeScript). Se comunican solo por la API HTTP y el WebSocket; el backend no sirve archivos de la interfaz.
- **Proceso worker**: único dueño de los contextos CUDA/OpenCL y del pool de decodificación. Al arrancar detecta y precalienta los backends; después ejecuta un trabajo a la vez recibido por una cola de órdenes y publica progreso, estados y resultados por una cola de eventos.
- **Proceso web del backend** (FastAPI + uvicorn en `127.0.0.1`): recibe subidas, las guarda en un directorio temporal, envía órdenes al worker, reenvía el progreso por WebSocket y sirve resultados. No hace cómputo pesado. Habilita CORS solo para el origen configurado del frontend.
- **Subida de archivos**: el lote (varios archivos o un `.zip`) y la imagen objetivo se suben como recursos separados, para poder reutilizar uno y cambiar el otro; validación de formatos y extracción segura del zip.
- **Interfaz en forma de stepper**:
  1. Imágenes: lote de teselas e imagen objetivo.
  2. Parámetros: columnas de la grilla, resolución de la tesela, opacidad de las teselas (el `alpha` del algoritmo, con nombre explicativo) y semilla, cada uno con un signo de pregunta que al pasar el mouse explica qué significa. `k` no se muestra: se usa el valor por defecto.
  3. Ejecución: CPU, GPU o ambas, según el hardware detectado. La opción GPU usa CUDA u OpenCL automáticamente según la placa disponible; si no hay GPU, GPU y "ambas" se ven deshabilitadas con el motivo.
  
  La interfaz es una sola pantalla: el stepper es la única navegación (sin sidebar ni menú global).

  Luego, progreso por etapa y pantalla de resultado con el fotomosaico, descarga y un botón "Ver estadísticas". "Volver a empezar" regresa al paso 1 con las imágenes anteriores ya cargadas, que se pueden cambiar.
- **Lenguaje visual** basado en el design system de `design.md` (se mueve a `TP-Integrador/frontend/DESIGN.md`): tokens de color, tipografía, espaciado y radios; un único acento azul; botones píldora; el mosaico como protagonista sobre un tile oscuro.
- **Script de arranque** (`start.sh` y `start.ps1`): crea un entorno virtual, instala lo que falte (dependencias de Python, la biblioteca de GPU que corresponda al hardware y Node.js dentro del venv si no está en el sistema), y levanta backend y frontend.
- Bloqueo de trabajos concurrentes: la interfaz lo impide y el servidor lo rechaza.

## Capabilities

### New Capabilities
- `arquitectura-de-procesos`: separación web/worker/pool, propiedad de los contextos de GPU, protocolo de colas (sin imágenes), un trabajo a la vez, arranque y apagado.
- `subida-de-archivos`: recepción, validación y almacenamiento temporal del lote (archivos sueltos o zip) y de la imagen objetivo como recursos separados y reutilizables.
- `interfaz-web`: pantalla única con stepper de imágenes, parámetros (con ayuda contextual) y forma de ejecución, con el lenguaje visual del design system; progreso; resultado con descarga y estadísticas; volver a empezar.
- `arranque-del-proyecto`: estructura backend/frontend, entorno virtual y script que instala lo necesario y levanta la aplicación.

### Modified Capabilities
<!-- Ninguna. -->

## Impact

- Código nuevo en `TP-Integrador/backend/app/worker/`, `backend/app/web/`, `backend/app/main.py`, `backend/app/config.py`, todo `TP-Integrador/frontend/` y los scripts `TP-Integrador/start.sh` y `start.ps1`.
- Dependencias nuevas en `backend/requirements.txt`: `fastapi`, `uvicorn`, `python-multipart`, `python-dotenv`; en `requirements-dev.txt`: `httpx` (cliente de tests de FastAPI). El script instala `nodeenv` en el venv solo si el sistema no tiene Node.js. En `frontend/package.json`: `react`, `react-dom`, `vite`, `typescript`, `eslint`, `stylelint`, `@fontsource/inter`, `vitest` y `@testing-library/react`.
- `backend/env.example`: host, puerto, origen permitido del frontend, directorio temporal y límites de subida. `frontend/env.example`: URL del backend.
- README: cómo levantar la aplicación con el script y cómo usar la interfaz.
