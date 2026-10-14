#!/usr/bin/env bash
# Corre las pruebas de integracion contra la API real (RF15). Requiere que
# la API y las 6 bases esten arriba (ver README, seccion "Orden de arranque").
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
pytest tests/integration -v
