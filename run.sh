#!/usr/bin/env bash
# Levanta Vortic completo: backend (Django) + frontend (Vite) juntos.
# Uso: ./run.sh   (desde la raíz del proyecto, donde están backend/ y frontend/)
# Ctrl+C corta los dos procesos.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/venv"

echo "== Vortic — arranque completo =="

# --- Backend ---
if [ ! -d "$VENV_DIR" ]; then
  echo "No encuentro el venv en $VENV_DIR — creándolo..."
  python3 -m venv "$VENV_DIR"
fi

echo "-> Activando venv e instalando dependencias (backend)..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install -q -r "$BACKEND_DIR/requirements.txt"

echo "-> Aplicando migraciones..."
python "$BACKEND_DIR/manage.py" migrate

echo "-> Levantando Django (puerto 8000) en segundo plano..."
python "$BACKEND_DIR/manage.py" runserver 0.0.0.0:8000 &
BACKEND_PID=$!

# Si el frontend falla o se corta, matar el backend también.
trap 'echo; echo "Cortando backend (PID $BACKEND_PID)..."; kill "$BACKEND_PID" 2>/dev/null' EXIT

# --- Frontend ---
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "-> Instalando dependencias del frontend (primera vez)..."
  (cd "$FRONTEND_DIR" && npm install)
fi

echo "-> Levantando frontend (Vite)..."
echo "   Backend:  http://localhost:8000/admin/"
echo "   Frontend: se abre la URL que muestre Vite (normalmente http://localhost:5173/)"
echo
(cd "$FRONTEND_DIR" && npm run dev)
