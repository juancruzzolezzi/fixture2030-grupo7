#!/usr/bin/env bash
# Levanta la API localmente (fuera de Docker), apuntando a las seis fuentes
# que trae docker-compose.yml. Variables de entorno: ver .env.example.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
set -a
[ -f .env ] && source .env
set +a
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
