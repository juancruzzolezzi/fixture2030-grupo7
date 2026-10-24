#!/usr/bin/env bash
# Hito 12 - Linea base: prepara los datos, prueba la hipotesis por separado,
# corre la carga con la API como en el Hito 10 (INFLUX_REUSAR_CLIENTE=0) y
# valida la integridad. Necesita las bases del Hito 10 levantadas y sembradas.
# No hace falta tener la API corriendo: la prueba levanta la suya en PUERTO_API.
set -euo pipefail
cd "$(dirname "$0")/.."
H10=../fixture2030-hito-10-api-integrada
# Python del venv del Hito 10 (Windows: Scripts/python.exe; Linux/Mac: bin/python)
if [ -x "$H10/.venv/Scripts/python.exe" ]; then PY="$H10/.venv/Scripts/python.exe"; else PY="$H10/.venv/bin/python"; fi
"$PY" -c "import psutil" 2>/dev/null || "$PY" -m pip install -q psutil   # para medir CPU y memoria de la API

echo "== 1/4 Preparar datos de laboratorio";  "$PY" scripts/preparar_datos.py
echo "== 2/4 Probar la hipotesis por separado"; "$PY" scripts/probar_hipotesis.py
echo "== 3/4 Carga (linea base)";             "$PY" scripts/ejecutar_carga.py --modo linea_base
echo "== 4/4 Integridad";                     "$PY" scripts/validar_integridad.py --modo linea_base
