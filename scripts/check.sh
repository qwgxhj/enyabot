#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ ! -d .venv ]]; then
  echo "[ERROR] Missing .venv" >&2
  exit 1
fi

source .venv/bin/activate
python -m compileall app

echo "[OK] Python files compile successfully."
