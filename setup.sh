#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)
VENV_PATH="$PROJECT_DIR/.venv"
FRONTEND_ENV="$PROJECT_DIR/frontend/.env.local"

if [ ! -d "$VENV_PATH" ]; then
  python3 -m venv "$VENV_PATH"
fi

# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"

pip install --upgrade pip
pip install -r "$PROJECT_DIR/backend/requirements.txt"

pushd "$PROJECT_DIR/frontend" >/dev/null
npm install
python3 - "$FRONTEND_ENV" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
desired = {
    "VITE_BACKEND_URL": "http://127.0.0.1",
    "VITE_BACKEND_PORT": "8000",
}
existing = {}
if path.exists():
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            existing[key.strip()] = value.strip()
existing.update(desired)
content = "\n".join(f"{key}={value}" for key, value in existing.items()) + "\n"
path.write_text(content)
PY
popd >/dev/null

echo "Environment is ready. Starting the FastAPI server..."
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
