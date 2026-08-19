#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ML_DIR="${SCRIPT_DIR}/../ml"

cd "$ML_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install google-cloud-aiplatform -q

echo "== ML ortami hazir =="
echo "Aktiflestirmek icin: source ${ML_DIR}/.venv/bin/activate"
