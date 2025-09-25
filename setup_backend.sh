#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)
VENV_PATH="$PROJECT_DIR/.venv"
BACKEND_HOST=${BACKEND_HOST:-0.0.0.0}
BACKEND_PORT=${BACKEND_PORT:-8010}

if [ ! -d "$VENV_PATH" ]; then
  python3 -m venv "$VENV_PATH"
fi

# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"

pip install --upgrade pip
pip install -r "$PROJECT_DIR/backend/requirements.txt"

export PYTHONPATH="$PROJECT_DIR/backend:${PYTHONPATH:-}"

uvicorn backend.app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload
