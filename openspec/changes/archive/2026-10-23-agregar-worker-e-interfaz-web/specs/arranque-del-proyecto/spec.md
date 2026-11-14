# Spec Delta

## Purpose

Permite levantar la aplicación completa (backend y frontend) con un único comando, instalando dentro de un entorno virtual lo que falte, incluida la biblioteca de GPU que corresponde al hardware, sin reinstalar lo que ya está.

## ADDED Requirements

### Requirement: Backend y frontend en carpetas separadas
El proyecto MUST organizarse en `TP-Integrador/backend/` (código Python, kernels, tests, `requirements*.txt` y su `env.example`) y `TP-Integrador/frontend/` (aplicación React + Vite con su `package.json` y su `env.example`). Cada uno MUST poder instalarse, probarse y ejecutarse por separado.

#### Scenario: Tests por separado
- **WHEN** se corren los tests del backend y los del frontend
- **THEN** cada suite corre desde su carpeta sin necesitar la otra

### Requirement: Dependencias en un entorno virtual
Todas las dependencias de Python MUST instalarse en un entorno virtual del proyecto (`TP-Integrador/.venv`), nunca en el Python del sistema. Si el sistema no tiene Node.js con la versión mínima requerida, Node MUST instalarse dentro de ese mismo entorno virtual.

#### Scenario: Máquina sin Node
- **WHEN** se ejecuta el script en una máquina sin `node` en el `PATH`
- **THEN** Node queda instalado dentro de `TP-Integrador/.venv` y el frontend se instala y se levanta con él

### Requirement: Script de arranque multiplataforma
El proyecto MUST incluir `start.sh` (macOS y Linux) y `start.ps1` (Windows) con el mismo comportamiento: crear el entorno virtual si no existe, instalar las dependencias que falten o hayan cambiado, crear los `.env` a partir de los `env.example` si no existen, levantar backend y frontend, e informar la URL de la interfaz. Ctrl+C MUST detener ambos sin dejar procesos huérfanos.

#### Scenario: Primer arranque
- **WHEN** se ejecuta `./start.sh` en una máquina recién clonada con Python instalado
- **THEN** se crea el venv, se instalan las dependencias, se levantan backend y frontend y se imprime la URL de la interfaz

#### Scenario: Arranques siguientes
- **WHEN** se vuelve a ejecutar el script sin cambios en `requirements*.txt` ni en `package-lock.json`
- **THEN** no se reinstala nada y la aplicación se levanta directamente

#### Scenario: Dependencias cambiadas
- **WHEN** se agregó una dependencia a `backend/requirements.txt` desde el último arranque
- **THEN** el script la instala antes de levantar la aplicación

### Requirement: Biblioteca de GPU según el hardware
El script MUST detectar la GPU e instalar la biblioteca que corresponde: PyCUDA si hay una placa NVIDIA, PyOpenCL en otro caso. Si la instalación de PyCUDA falla, MUST intentar PyOpenCL. Una falla de instalación de GPU MUST informarse como advertencia sin impedir el arranque con CPU, y MUST NOT reintentarse en cada arranque salvo que se pida explícitamente. MUST existir una opción para saltear la instalación de GPU.

#### Scenario: Placa NVIDIA con CUDA Toolkit
- **WHEN** `nvidia-smi` responde y el CUDA Toolkit está instalado
- **THEN** se instala PyCUDA y en el paso 3 de la interfaz la GPU aparece como CUDA

#### Scenario: Placa NVIDIA sin CUDA Toolkit
- **WHEN** `nvidia-smi` responde pero PyCUDA no se puede compilar
- **THEN** se informa la advertencia, se instala PyOpenCL y la GPU aparece como OpenCL sobre la misma placa

#### Scenario: Máquina sin GPU compatible
- **WHEN** no se puede instalar ninguna biblioteca de GPU
- **THEN** la aplicación arranca, la advertencia queda impresa y en la interfaz solo se puede elegir CPU

### Requirement: Comprobación de requisitos previos
El script MUST verificar que Python cumple la versión mínima antes de crear el entorno virtual y, si no la cumple, MUST terminar con un mensaje que indique la versión requerida y la encontrada.

#### Scenario: Python viejo
- **WHEN** el Python del sistema es anterior a la versión mínima
- **THEN** el script termina sin crear el venv e indica qué versión instalar
