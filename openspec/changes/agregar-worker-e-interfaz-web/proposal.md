# Proposal

## Why

Los backends y la carga común (cambios 1 y 2) solo se pueden usar desde tests. Para que el TP sirva como demostración hace falta una aplicación local donde una persona suba un lote de teselas y una imagen objetivo, elija el backend, vea el progreso por etapa y obtenga el mosaico junto con la tabla de tiempos. Además, los contextos de GPU y el cómputo pesado tienen que vivir fuera del proceso web para que la interfaz no se bloquee y para respetar las reglas de CUDA sobre procesos.

Es el **cambio 3 de 5**. Depende de los cambios 1 y 2.

## What Changes

- **Proceso worker**: único dueño de los contextos CUDA/OpenCL y del pool de decodificación. Al arrancar detecta y precalienta los backends; después ejecuta un trabajo a la vez recibido por una cola de órdenes y publica progreso, estados y resultados por una cola de eventos.
- **Proceso web** (FastAPI + uvicorn en `127.0.0.1`): recibe subidas, las guarda en un directorio temporal, envía órdenes al worker, reenvía el progreso por WebSocket y sirve resultados. No hace cómputo pesado.
- **Subida de archivos**: varios archivos o un `.zip` para el lote, y la imagen objetivo; validación de formatos y extracción segura del zip.
- **Interfaz web** (HTML + JS sin frameworks): parámetros, selector de backend con el estado de cada uno y "Automático", información del problema (N, M, M·N, tamaño final), barra de progreso por etapa, vista previa con zoom, descargas PNG/JPEG, tabla de tiempos y advertencia con estimación para trabajos largos en CPU.
- Bloqueo de trabajos concurrentes: la interfaz lo impide y el servidor lo rechaza.

## Capabilities

### New Capabilities
- `arquitectura-de-procesos`: separación web/worker/pool, propiedad de los contextos de GPU, protocolo de colas (sin imágenes), un trabajo a la vez, arranque y apagado.
- `subida-de-archivos`: recepción, validación y almacenamiento temporal del lote (archivos sueltos o zip) y de la imagen objetivo.
- `interfaz-web`: pantallas y comportamientos visibles para configurar, ejecutar, seguir y descargar un trabajo con un backend.

### Modified Capabilities
<!-- Ninguna. -->

## Impact

- Código nuevo en `TP-Integrador/app/worker/`, `app/web/`, `app/main.py`, `app/config.py` y `static/`.
- Dependencias nuevas en `requirements.txt`: `fastapi`, `uvicorn`, `python-multipart`; en `requirements-dev.txt`: `httpx` (cliente de tests de FastAPI).
- `env.example`: host, puerto, directorio temporal y límites de subida.
- README: cómo ejecutar la aplicación y cómo usar la interfaz.
