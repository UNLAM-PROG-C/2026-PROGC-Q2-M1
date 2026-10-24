# Tareas del backend. Usa el Python del entorno virtual TP-Integrador/.venv.
# En Windows sin make, ver los comandos equivalentes en TP-Integrador/README.md.

ifeq ($(OS),Windows_NT)
PYTHON ?= ../.venv/Scripts/python.exe
else
PYTHON ?= ../.venv/bin/python
endif

CLANG_FORMAT ?= clang-format

.PHONY: build test lint lint-kernels format backends bench run clean

# Compila a bytecode todo el paquete (detecta errores de sintaxis).
build:
	$(PYTHON) -m compileall -q app tests

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

# Verifica el formato de los kernels con el .clang-format de la raíz del repo (Allman).
lint-kernels:
	$(CLANG_FORMAT) --dry-run --Werror kernels/mosaic.cu kernels/mosaic.cl

# Diagnóstico: estado de CPU, CUDA y OpenCL, y GPU preferida.
backends:
	$(PYTHON) -m app.backends.registry

# Benchmark sin interfaz con los valores por defecto; deja tabla, CSV y PNG en resultados/.
bench:
	$(PYTHON) benchmark.py

# Levanta el backend (proceso web + worker) en MOSAIC_HOST:MOSAIC_PORT. Ctrl+C lo apaga.
run:
	$(PYTHON) -m app.main

# Aplica el formato de ruff (2 espacios).
format:
	$(PYTHON) -m ruff format .

# Borra cachés de Python, pytest y ruff.
clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in [*pathlib.Path('.').rglob('__pycache__'), pathlib.Path('.pytest_cache'), pathlib.Path('.ruff_cache')]]"
