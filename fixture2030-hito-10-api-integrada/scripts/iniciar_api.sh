#!/usr/bin/env bash
# Levanta la API localmente (fuera de Docker), apuntando a las seis fuentes
# que trae docker-compose.yml. Variables de entorno: ver .env.example.
set -euo pipefail
cd "$(dirname "$0")/.."
# Linux/Mac: .venv/bin ; Windows (Git Bash): .venv/Scripts
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; else source .venv/Scripts/activate; fi
set -a
[ -f .env ] && source <(tr -d '\r' < .env)   # tr: por si el .env tiene fin de linea de Windows
set +a
# El log tambien queda en api.log (no se versiona): el Hito 11 lo usa para
# relacionar cada request_id con sus lineas de log.
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload 2>&1 | tee -a api.log
