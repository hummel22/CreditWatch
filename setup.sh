#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)
VENV_PATH="$PROJECT_DIR/.venv"

if [ ! -d "$VENV_PATH" ]; then
  python3 -m venv "$VENV_PATH"
fi

# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"

pip install --upgrade pip
pip install -r "$PROJECT_DIR/backend/requirements.txt"

pushd "$PROJECT_DIR/frontend" >/dev/null
npm install
popd >/dev/null

echo "Environment is ready. Starting the FastAPI server..."
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
