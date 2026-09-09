# TP1 - Parte 1 - Ejercicio 2: Monitor de Jurassic Park
# Programacion Concurrente - UNLaM - Modalidad 1
#
# Uso rapido:
#   make build
#   make run
#   make run DURATION=30 INTERVAL=1

# Interprete: prioriza python3 (Linux/macOS/Colab) y cae en python (Windows).
PYTHON ?= $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)

SRC_DIR  := src
MAIN     := $(SRC_DIR)/jurassic_park_monitor.py

# Parametros del monitoreo (sobreescribibles desde la linea de comandos).
DURATION ?= 12
INTERVAL ?= 2

.PHONY: help build run clean

help:
	@echo "Targets disponibles:"
	@echo "  make build   - verifica sintaxis y genera el bytecode (__pycache__)"
	@echo "  make run     - ejecuta el monitor (DURATION=$(DURATION)s, INTERVAL=$(INTERVAL)s)"
	@echo "  make clean   - borra el bytecode generado"
	@echo ""
	@echo "Ejemplo: make run DURATION=30 INTERVAL=1"

# En Python no hay linkeo: buildear es compilar a bytecode, que ademas valida la sintaxis.
build:
	$(PYTHON) -m compileall -q $(SRC_DIR)

run: build
	$(PYTHON) $(MAIN) --duration $(DURATION) --interval $(INTERVAL)

clean:
	rm -rf $(SRC_DIR)/__pycache__
