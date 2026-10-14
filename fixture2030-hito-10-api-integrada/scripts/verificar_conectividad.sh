#!/usr/bin/env bash
# Prueba real de conectividad contra las seis fuentes, via GET /salud de la
# propia API (RF17, RNF11). Requiere que la API este corriendo.
set -euo pipefail
URL="${1:-http://localhost:8000}/salud"
echo "Consultando $URL ..."
curl -sf "$URL" | python3 -m json.tool
