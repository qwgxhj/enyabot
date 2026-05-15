#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ ! -d .venv ]]; then
  echo "[ERROR] Virtual environment .venv not found. Run scripts/install_ubuntu.sh first." >&2
  exit 1
fi

source .venv/bin/activate
exec python3 -m app.main
