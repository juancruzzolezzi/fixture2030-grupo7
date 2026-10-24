#!/usr/bin/env bash
# Hito 12 - Repite exactamente el mismo escenario con el cambio activado
# (INFLUX_REUSAR_CLIENTE=1), valida la integridad y arma la comparacion.
# Correr despues de ejecutar_linea_base.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
H10=../fixture2030-hito-10-api-integrada
if [ -x "$H10/.venv/Scripts/python.exe" ]; then PY="$H10/.venv/Scripts/python.exe"; else PY="$H10/.venv/bin/python"; fi

echo "== 1/3 Carga (optimizada)"; "$PY" scripts/ejecutar_carga.py --modo optimizada
echo "== 2/3 Integridad";         "$PY" scripts/validar_integridad.py --modo optimizada
echo "== 3/3 Comparacion";        "$PY" scripts/comparar.py
