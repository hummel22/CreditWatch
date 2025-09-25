#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)
FRONTEND_DIR="$PROJECT_DIR/frontend"
FRONTEND_ENV="$FRONTEND_DIR/.env.local"
FRONTEND_HOST=${FRONTEND_HOST:-0.0.0.0}
FRONTEND_PORT=${FRONTEND_PORT:-4173}
BACKEND_URL=${BACKEND_URL:-http://127.0.0.1}
BACKEND_PORT=${BACKEND_PORT:-8010}

pushd "$FRONTEND_DIR" >/dev/null

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to build the frontend." >&2
  exit 1
fi

npm install

python3 - "$FRONTEND_ENV" "$BACKEND_URL" "$BACKEND_PORT" <<'PY'
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
backend_url, backend_port = sys.argv[2:4]
values = {
    "VITE_BACKEND_URL": backend_url,
    "VITE_BACKEND_PORT": backend_port,
}
existing = {}
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            existing[key.strip()] = value.strip()
existing.update(values)
content = "\n".join(f"{key}={value}" for key, value in existing.items()) + "\n"
env_path.write_text(content)
PY

npm run build
npm run preview -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"

popd >/dev/null
