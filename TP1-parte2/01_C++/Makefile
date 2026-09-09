# TP1 - Parte 2 - Ejercicio 1: El entrenamiento de Naruto Uzumaki
# Programacion Concurrente - UNLaM - Modalidad 1
#
# Uso rapido:
#   make build
#   make run
#   make run CLONES=20

CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -pthread
LDFLAGS  ?= -pthread

SRC_DIR := src
MAIN    := $(SRC_DIR)/naruto_training.cpp

# En Windows el ejecutable lleva extension .exe; en Linux/macOS/Colab no.
ifeq ($(OS),Windows_NT)
    BIN := naruto_training.exe
else
    BIN := naruto_training
endif

# Cantidad de clones de sombra (sobreescribible desde la linea de comandos).
CLONES ?= 10

.PHONY: help build run clean

help:
	@echo "Targets disponibles:"
	@echo "  make build   - compila $(MAIN) y genera $(BIN)"
	@echo "  make run     - ejecuta el entrenamiento con CLONES=$(CLONES) clones"
	@echo "  make clean   - borra el ejecutable generado"
	@echo ""
	@echo "Ejemplo: make run CLONES=20"

build: $(BIN)

# -pthread es obligatorio: sin el, std::thread compila pero falla en tiempo de ejecucion
# en varias distribuciones de Linux (incluida la de Colab).
$(BIN): $(MAIN)
	$(CXX) $(CXXFLAGS) -o $(BIN) $(MAIN) $(LDFLAGS)

run: build
	./$(BIN) $(CLONES)

clean:
	rm -f $(BIN)
