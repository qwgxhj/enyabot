#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  echo "[WARN] You are running as root. A normal service user is recommended."
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$PROJECT_DIR"

if [[ ! -f requirements.txt ]]; then
  echo "[ERROR] requirements.txt not found in $PROJECT_DIR" >&2
  exit 1
fi

sudo apt update
sudo apt install -y python3 python3-venv python3-pip git curl

if [[ ! -d .venv ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

mkdir -p data/logs personas

if [[ ! -f .env ]]; then
  if [[ -f .env.production.example ]]; then
    cp .env.production.example .env
  else
    cp .env.example .env
  fi
  echo "[INFO] Created .env. Please edit it before first production start."
fi

if [[ ! -f config.yaml && -f config.example.yaml ]]; then
  cp config.example.yaml config.yaml
  echo "[INFO] Created config.yaml from config.example.yaml"
fi

if [[ ! -f data/.gitkeep ]]; then
  touch data/.gitkeep
fi

cat <<EOF
[OK] Ubuntu dependencies installed.
Project directory: $PROJECT_DIR
Next steps:
  1. Edit: $PROJECT_DIR/.env
  2. Edit: $PROJECT_DIR/config.yaml
  3. Start: $PROJECT_DIR/scripts/start.sh
EOF
