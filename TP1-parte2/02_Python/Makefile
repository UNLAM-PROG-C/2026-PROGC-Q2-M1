# TP1 - Parte 2 - Ejercicio 2: Combates Eternos en el Netherrealm
# Programacion Concurrente - UNLaM - Modalidad 1
#
# Uso rapido:
#   make build
#   make run
#   make run TORNEOS=100000 HILOS=8
#   make bench

# En Windows el interprete se llama "python"; en Linux/macOS/Colab, "python3".
ifeq ($(OS),Windows_NT)
    PYTHON ?= python
else
    PYTHON ?= python3
endif

SRC_DIR := src
MAIN    := $(SRC_DIR)/mortal_kombat.py

# Parametros de la simulacion (sobreescribibles desde la linea de comandos).
TORNEOS ?= 10000
HILOS   ?= 4

# Cantidades de hilos que compara el target bench.
BENCH_HILOS    ?= 1 2 4 8 16
BENCH_TORNEOS  ?= 20000

.PHONY: help build run bench deps clean

help:
	@echo "Targets disponibles:"
	@echo "  make build   - verifica la sintaxis y genera el bytecode de $(MAIN)"
	@echo "  make run     - simula TORNEOS=$(TORNEOS) torneos con HILOS=$(HILOS) hilos"
	@echo "  make bench   - mide el tiempo con $(BENCH_HILOS) hilos ($(BENCH_TORNEOS) torneos)"
	@echo "  make deps    - instala las dependencias del cuaderno (matplotlib)"
	@echo "  make clean   - borra el bytecode generado (__pycache__)"
	@echo ""
	@echo "Ejemplo: make run TORNEOS=100000 HILOS=8"

# Python es interpretado: "buildear" es compilar a bytecode, que ademas valida la sintaxis.
build:
	$(PYTHON) -m compileall -q $(MAIN)

run: build
	$(PYTHON) $(MAIN) $(TORNEOS) $(HILOS)

bench: build
	@for n in $(BENCH_HILOS); do \
		$(PYTHON) $(MAIN) $(BENCH_TORNEOS) $$n | grep "Tiempo total" | sed "s/^/hilos=$$n -> /"; \
	done

# Solo hace falta para reproducir el grafico del cuaderno: el programa usa unicamente
# la biblioteca estandar.
deps:
	$(PYTHON) -m pip install -r requirements.txt

clean:
	rm -rf $(SRC_DIR)/__pycache__
