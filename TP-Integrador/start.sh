#!/usr/bin/env bash
# Script de arranque de la aplicación (macOS y Linux). Equivalente a start.ps1.
#
# Pasos (cada uno idempotente, ver design D11 del cambio agregar-worker-e-interfaz-web):
#   1. Verifica la versión de Python y crea TP-Integrador/.venv si no existe.
#   2. Instala backend/requirements.txt si cambió desde la última instalación.
#   3. Instala la biblioteca de GPU: PyCUDA si hay placa NVIDIA, PyOpenCL si no
#      (o si PyCUDA falla). Una falla es solo una advertencia y no se reintenta
#      hasta que cambien los requirements de GPU o se pase --reinstall.
#   4. Usa el node del PATH si cumple la versión mínima; si no, instala Node LTS
#      dentro del venv con nodeenv. Corre npm ci si cambió package-lock.json.
#   5. Crea backend/.env y frontend/.env a partir de env.example si no existen.
#   6. Levanta backend y frontend; Ctrl+C detiene ambos sin dejar huérfanos.
#
# Las huellas de lo instalado se guardan en .venv/.mosaic-stamp (formato clave=valor,
# compartido con start.ps1).
#
# Uso: ./start.sh [--cpu-only] [--reinstall] [--help]

set -euo pipefail

readonly MIN_PYTHON_MAJOR=3
readonly MIN_PYTHON_MINOR=11
readonly MIN_NODE_MAJOR=20
readonly MIN_NODE_MINOR=19
readonly DEFAULT_BACKEND_HOST="127.0.0.1"
readonly DEFAULT_BACKEND_PORT=8000
readonly DEFAULT_FRONTEND_HOST="127.0.0.1"
readonly DEFAULT_FRONTEND_PORT=5173
readonly BACKEND_READY_TIMEOUT_S=180
readonly FRONTEND_READY_TIMEOUT_S=60
readonly HTTP_PROBE_TIMEOUT_S=2
readonly POLL_INTERVAL_S=1
readonly SHUTDOWN_GRACE_S=10
readonly BACKEND_STATE_PATH="/api/state"

readonly GPU_RESULT_CUDA="cuda"
readonly GPU_RESULT_OPENCL="opencl"
readonly GPU_RESULT_NONE="none"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly ROOT_DIR
readonly BACKEND_DIR="$ROOT_DIR/backend"
readonly FRONTEND_DIR="$ROOT_DIR/frontend"
readonly VENV_DIR="$ROOT_DIR/.venv"
readonly STAMP_FILE="$VENV_DIR/.mosaic-stamp"

CPU_ONLY=false
REINSTALL=false
VENV_BIN=""
VENV_PY=""
BACKEND_PID=""
FRONTEND_PID=""
CLEANED_UP=false

log()
{
  printf '[start] %s\n' "$*"
}

warn()
{
  printf '[start] ADVERTENCIA: %s\n' "$*" >&2
}

die()
{
  printf '[start] ERROR: %s\n' "$*" >&2
  exit 1
}

print_usage()
{
  cat <<'EOF'
Uso: ./start.sh [opciones]

  --cpu-only    No instala la biblioteca de GPU (PyCUDA/PyOpenCL).
  --reinstall   Ignora las huellas guardadas: reinstala dependencias de Python,
                reintenta la biblioteca de GPU y vuelve a correr npm ci.
  -h, --help    Muestra esta ayuda.
EOF
}

parse_args()
{
  local arg
  for arg in "$@"
  do
    case "$arg" in
      --cpu-only) CPU_ONLY=true ;;
      --reinstall) REINSTALL=true ;;
      -h | --help)
        print_usage
        exit 0
        ;;
      *)
        print_usage >&2
        die "opción desconocida: $arg"
        ;;
    esac
  done
}

# --- Huella de instalación (.venv/.mosaic-stamp) ------------------------------------

stamp_get()
{
  if [ -f "$STAMP_FILE" ]
  then
    sed -n "s/^$1=//p" "$STAMP_FILE" | tr -d '\r' | head -n 1
  fi
}

stamp_set()
{
  local tmp_file="$STAMP_FILE.tmp"
  {
    if [ -f "$STAMP_FILE" ]
    then
      grep -v "^$1=" "$STAMP_FILE" | tr -d '\r' || true
    fi
    printf '%s=%s\n' "$1" "$2"
  } >"$tmp_file"
  mv "$tmp_file" "$STAMP_FILE"
}

# Huella SHA-256 del contenido de los archivos (misma fórmula que start.ps1).
files_hash()
{
  "$VENV_PY" -c 'import hashlib,sys,pathlib; h=hashlib.sha256(); [h.update(pathlib.Path(p).read_bytes()) for p in sys.argv[1:]]; print(h.hexdigest())' "$@"
}

# Devuelve 0 si la huella guardada en "key" coincide con "hash" y no se pidió --reinstall.
stamp_matches()
{
  [ "$REINSTALL" = false ] && [ "$(stamp_get "$1")" = "$2" ]
}

# --- Paso 1: Python y entorno virtual ------------------------------------------------

python_meets_minimum()
{
  "$1" -c "import sys; sys.exit(0 if sys.version_info[:2] >= ($MIN_PYTHON_MAJOR, $MIN_PYTHON_MINOR) else 1)" >/dev/null 2>&1
}

python_version_of()
{
  "$1" -c 'import platform; print(platform.python_version())' 2>/dev/null || echo "desconocida"
}

find_system_python()
{
  local candidate
  local found_versions=""
  for candidate in python3 python
  do
    if command -v "$candidate" >/dev/null 2>&1
    then
      if python_meets_minimum "$candidate"
      then
        echo "$candidate"
        return 0
      fi
      found_versions="$found_versions $candidate=$(python_version_of "$candidate")"
    fi
  done
  die "se necesita Python >= $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR (encontrado:${found_versions:- ninguno}). Instalalo y volvé a correr el script."
}

resolve_venv_paths()
{
  # En Git Bash (Windows) el venv usa Scripts/ en lugar de bin/.
  if [ -x "$VENV_DIR/Scripts/python.exe" ]
  then
    VENV_BIN="$VENV_DIR/Scripts"
    VENV_PY="$VENV_BIN/python.exe"
  else
    VENV_BIN="$VENV_DIR/bin"
    VENV_PY="$VENV_BIN/python"
  fi
}

ensure_venv()
{
  resolve_venv_paths
  if [ -x "$VENV_PY" ]
  then
    python_meets_minimum "$VENV_PY" || die "el venv usa Python $(python_version_of "$VENV_PY") y se necesita >= $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR. Borrá .venv y volvé a correr el script."
    return 0
  fi
  local system_python
  system_python="$(find_system_python)"
  log "Creando el entorno virtual en .venv con $system_python $(python_version_of "$system_python")..."
  "$system_python" -m venv "$VENV_DIR" || die "no se pudo crear el venv (en Debian/Ubuntu: instalar python3-venv)."
  resolve_venv_paths
}

pip_install()
{
  "$VENV_PY" -m pip install --disable-pip-version-check "$@"
}

# --- Paso 2: dependencias de Python ---------------------------------------------------

ensure_python_requirements()
{
  local requirements_hash
  requirements_hash="$(files_hash "$BACKEND_DIR/requirements.txt")"
  if stamp_matches python "$requirements_hash"
  then
    log "Dependencias de Python al día."
    return 0
  fi
  log "Instalando backend/requirements.txt..."
  pip_install -r "$BACKEND_DIR/requirements.txt" || die "falló la instalación de backend/requirements.txt."
  stamp_set python "$requirements_hash"
}

# --- Paso 3: biblioteca de GPU ---------------------------------------------------------

has_nvidia_gpu()
{
  command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1
}

# Intenta PyCUDA (solo con NVIDIA) y cae a PyOpenCL; imprime el resultado.
install_gpu_library()
{
  if has_nvidia_gpu
  then
    log "Placa NVIDIA detectada: instalando PyCUDA (requirements-cuda.txt)..." >&2
    if pip_install -r "$BACKEND_DIR/requirements-cuda.txt" >&2
    then
      echo "$GPU_RESULT_CUDA"
      return 0
    fi
    warn "no se pudo instalar PyCUDA (¿falta el CUDA Toolkit?). Se intenta PyOpenCL sobre la misma placa."
  else
    log "Sin placa NVIDIA: instalando PyOpenCL (requirements-opencl.txt)..." >&2
  fi
  if pip_install -r "$BACKEND_DIR/requirements-opencl.txt" >&2
  then
    echo "$GPU_RESULT_OPENCL"
    return 0
  fi
  echo "$GPU_RESULT_NONE"
}

ensure_gpu_library()
{
  if [ "$CPU_ONLY" = true ]
  then
    log "--cpu-only: se saltea la instalación de la biblioteca de GPU."
    return 0
  fi
  local gpu_hash gpu_result
  gpu_hash="$(files_hash "$BACKEND_DIR/requirements-cuda.txt" "$BACKEND_DIR/requirements-opencl.txt")"
  if stamp_matches gpu "$gpu_hash"
  then
    log "Biblioteca de GPU ya decidida: $(stamp_get gpu_result) (usar --reinstall para reintentar)."
    return 0
  fi
  gpu_result="$(install_gpu_library)"
  if [ "$gpu_result" = "$GPU_RESULT_NONE" ]
  then
    warn "no se pudo instalar ninguna biblioteca de GPU: la aplicación arranca solo con CPU. Reintentar con --reinstall."
  fi
  stamp_set gpu "$gpu_hash"
  stamp_set gpu_result "$gpu_result"
}

# --- Paso 4: Node y dependencias del frontend ----------------------------------------

node_meets_minimum()
{
  command -v node >/dev/null 2>&1 || return 1
  local version major minor
  version="$(node --version 2>/dev/null)" || return 1
  version="${version#v}"
  major="${version%%.*}"
  minor="${version#*.}"
  minor="${minor%%.*}"
  [ "$major" -gt "$MIN_NODE_MAJOR" ] || { [ "$major" -eq "$MIN_NODE_MAJOR" ] && [ "$minor" -ge "$MIN_NODE_MINOR" ]; }
}

ensure_node()
{
  # Con el venv primero en el PATH, un Node instalado por nodeenv tiene prioridad.
  export PATH="$VENV_BIN:$PATH"
  if node_meets_minimum
  then
    log "Node $(node --version) disponible."
    return 0
  fi
  log "No hay Node >= $MIN_NODE_MAJOR.$MIN_NODE_MINOR en el PATH: instalando Node LTS dentro del venv con nodeenv..."
  pip_install nodeenv || die "no se pudo instalar nodeenv."
  VIRTUAL_ENV="$VENV_DIR" "$VENV_PY" -m nodeenv --python-virtualenv --node=lts || die "nodeenv no pudo instalar Node."
  hash -r
  node_meets_minimum || die "Node instalado con nodeenv no cumple la versión mínima."
  log "Node $(node --version) instalado en el venv."
}

ensure_frontend_dependencies()
{
  local lock_hash
  lock_hash="$(files_hash "$FRONTEND_DIR/package-lock.json")"
  if [ -d "$FRONTEND_DIR/node_modules" ] && stamp_matches npm "$lock_hash"
  then
    log "Dependencias del frontend al día."
    return 0
  fi
  log "Instalando dependencias del frontend (npm ci)..."
  (cd "$FRONTEND_DIR" && npm ci) || die "falló npm ci en frontend/."
  stamp_set npm "$lock_hash"
}

# --- Paso 5: archivos .env -------------------------------------------------------------

ensure_env_file()
{
  if [ ! -f "$1/.env" ]
  then
    cp "$1/env.example" "$1/.env"
    log "Creado $(basename "$1")/.env a partir de env.example."
  fi
}

# Quita espacios al principio y al final, y las comillas que envuelvan el valor.
clean_env_value()
{
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  value="${value#[\"\']}"
  value="${value%[\"\']}"
  echo "$value"
}

# Valor de una variable: entorno, si no el .env indicado, si no el valor por defecto.
env_value()
{
  local file="$1" key="$2" default="$3" value=""
  if [ -n "${!key:-}" ]
  then
    echo "${!key}"
    return 0
  fi
  if [ -f "$file" ]
  then
    value="$(clean_env_value "$(sed -n "s/^[[:space:]]*$key[[:space:]]*=//p" "$file" | tr -d '\r' | tail -n 1)")"
  fi
  echo "${value:-$default}"
}

# Exporta las variables de un .env que no estén ya definidas en el entorno
# (las constantes del backend se leen al importar, antes que el .env opcional).
export_env_file()
{
  local line key value
  [ -f "$1" ] || return 0
  while IFS= read -r line || [ -n "$line" ]
  do
    line="${line%$'\r'}"
    case "$line" in
      '' | '#'*) continue ;;
    esac
    key="${line%%=*}"
    key="${key//[[:space:]]/}"
    value="$(clean_env_value "${line#*=}")"
    if [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && [ -z "${!key+set}" ]
    then
      export "$key=$value"
    fi
  done <"$1"
}

# --- Paso 6: procesos de backend y frontend --------------------------------------------

url_responds()
{
  "$VENV_PY" -c "import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=$HTTP_PROBE_TIMEOUT_S)" "$1" >/dev/null 2>&1
}

process_alive()
{
  [ -n "$1" ] && kill -0 "$1" 2>/dev/null
}

wait_for_url()
{
  local url="$1" pid="$2" timeout_s="$3" waited_s=0
  until url_responds "$url"
  do
    process_alive "$pid" || die "el proceso terminó antes de responder en $url."
    [ "$waited_s" -lt "$timeout_s" ] || die "$url no respondió en $timeout_s s."
    sleep "$POLL_INTERVAL_S"
    waited_s=$((waited_s + POLL_INTERVAL_S))
  done
}

# Backend y frontend se lanzan con job control (set -m) solo durante el fork: cada
# uno queda en su propio grupo de procesos, así se señaliza el grupo entero (worker
# de Python, Vite, etc.) y el Ctrl+C de la terminal le llega solo a este script.
signal_group()
{
  if process_alive "$2"
  then
    kill "-$1" -- "-$2" 2>/dev/null || kill "-$1" "$2" 2>/dev/null || true
  fi
}

group_alive()
{
  [ -n "$1" ] && { kill -0 -- "-$1" 2>/dev/null || kill -0 "$1" 2>/dev/null; }
}

cleanup()
{
  [ "$CLEANED_UP" = false ] || return 0
  CLEANED_UP=true
  trap - INT TERM
  [ -n "$BACKEND_PID$FRONTEND_PID" ] || return 0
  log "Deteniendo backend y frontend..."
  # SIGINT al backend: uvicorn hace el apagado ordenado (lifespan) y detiene al worker.
  signal_group INT "$BACKEND_PID"
  signal_group TERM "$FRONTEND_PID"
  local waited_s=0
  while { group_alive "$BACKEND_PID" || group_alive "$FRONTEND_PID"; } && [ "$waited_s" -lt "$SHUTDOWN_GRACE_S" ]
  do
    sleep "$POLL_INTERVAL_S"
    waited_s=$((waited_s + POLL_INTERVAL_S))
  done
  signal_group KILL "$BACKEND_PID"
  signal_group KILL "$FRONTEND_PID"
  log "Listo."
}

on_interrupt()
{
  exit 130
}

start_processes()
{
  local backend_host backend_port frontend_port backend_url frontend_url
  backend_host="$(env_value "$BACKEND_DIR/.env" MOSAIC_HOST "$DEFAULT_BACKEND_HOST")"
  backend_port="$(env_value "$BACKEND_DIR/.env" MOSAIC_PORT "$DEFAULT_BACKEND_PORT")"
  frontend_port="$(env_value "$FRONTEND_DIR/.env" FRONTEND_PORT "$DEFAULT_FRONTEND_PORT")"
  backend_url="http://$backend_host:$backend_port"
  frontend_url="http://$DEFAULT_FRONTEND_HOST:$frontend_port"

  trap cleanup EXIT
  trap on_interrupt INT TERM
  log "Levantando el backend en $backend_url..."
  set -m
  (cd "$BACKEND_DIR" && export_env_file .env && exec "$VENV_PY" -m app.main) </dev/null &
  BACKEND_PID=$!
  set +m
  wait_for_url "$backend_url$BACKEND_STATE_PATH" "$BACKEND_PID" "$BACKEND_READY_TIMEOUT_S"
  log "Levantando el frontend..."
  set -m
  (cd "$FRONTEND_DIR" && exec npm run dev) </dev/null &
  FRONTEND_PID=$!
  set +m
  wait_for_url "$frontend_url" "$FRONTEND_PID" "$FRONTEND_READY_TIMEOUT_S"
  log "Aplicación lista: abrí $frontend_url (Ctrl+C para detener)."
}

wait_while_running()
{
  while process_alive "$BACKEND_PID" && process_alive "$FRONTEND_PID"
  do
    sleep "$POLL_INTERVAL_S"
  done
  warn "uno de los procesos terminó; se detiene el resto."
}

main()
{
  parse_args "$@"
  ensure_venv
  ensure_python_requirements
  ensure_gpu_library
  ensure_node
  ensure_frontend_dependencies
  ensure_env_file "$BACKEND_DIR"
  ensure_env_file "$FRONTEND_DIR"
  start_processes
  wait_while_running
}

main "$@"
