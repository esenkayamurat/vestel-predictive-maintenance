#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="${SCRIPT_DIR}/../cloud-run-api"

cd "$API_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "== Kurulum tamam =="
echo "API'yi baslatmak icin:"
echo "  cd ${API_DIR}"
echo "  source .venv/bin/activate"
echo "  uvicorn main:app --reload --port 8080"
