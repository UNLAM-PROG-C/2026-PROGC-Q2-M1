# Tareas del backend. Usa el Python del entorno virtual TP-Integrador/.venv.
# En Windows sin make, ver los comandos equivalentes en TP-Integrador/README.md.

ifeq ($(OS),Windows_NT)
PYTHON ?= ../.venv/Scripts/python.exe
else
PYTHON ?= ../.venv/bin/python
endif

.PHONY: build test lint format clean

# Compila a bytecode todo el paquete (detecta errores de sintaxis).
build:
	$(PYTHON) -m compileall -q app tests

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

# Aplica el formato de ruff (2 espacios).
format:
	$(PYTHON) -m ruff format .

# Borra cachés de Python, pytest y ruff.
clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in [*pathlib.Path('.').rglob('__pycache__'), pathlib.Path('.pytest_cache'), pathlib.Path('.ruff_cache')]]"
