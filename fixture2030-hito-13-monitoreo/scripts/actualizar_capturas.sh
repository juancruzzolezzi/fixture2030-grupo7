#!/usr/bin/env bash
# Hito 13 - Recarga el dashboard en Grafana, rehace sus capturas de la ultima corrida, commitea y
# pregunta antes de subir. No toca las bases ni las metricas. Lo lanza actualizar_capturas.bat.
set -uo pipefail
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
H10="$RAIZ/fixture2030-hito-10-api-integrada"
H13="$RAIZ/fixture2030-hito-13-monitoreo"
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
mkdir -p "$H13/trabajo"
exec > >(tee -a "$H13/trabajo/corrida.log") 2>&1
parar() { echo; echo "SE DETUVO: $1"; exit 1; }
if [ -f "$H10/.venv/Scripts/python.exe" ]; then PY="$H10/.venv/Scripts/python.exe"; else PY="$H10/.venv/bin/python"; fi
cd "$H13" || exit 1
echo "=== Recargando Grafana (conserva sus datos)"
docker compose --env-file ../fixture2030-hito-10-api-integrada/.env --env-file .env up -d --force-recreate grafana || parar "no se pudo recrear Grafana"
echo "=== Rehaciendo las capturas"
if ! "$PY" scripts/recapturar.py; then
  docker logs --tail 40 fixture2030-grafana 2>&1 | grep -iE 'provision|dashboard' | tail -10
  parar "no se pudieron rehacer las capturas. Pasale esta salida a Claude."
fi
cd "$RAIZ" || exit 1
git add fixture2030-hito-13-monitoreo
if ! git diff --cached --quiet; then git commit -q -m "Hito 13: capturas con el dashboard corregido" || parar "fallo el commit"; fi
git log -1 --format='%h %s'
echo
echo "Mira 01_estado_normal.png y 03_falla_redis.png en fixture2030-hito-13-monitoreo/evidencia/dashboards"
read -r -p "Subir a GitHub (rama $(git rev-parse --abbrev-ref HEAD))? [s/N] " RESPUESTA
if [ "$RESPUESTA" = "s" ] || [ "$RESPUESTA" = "S" ]; then
  git pull -q --ff-only origin "$(git rev-parse --abbrev-ref HEAD)" || parar "el remoto tiene cambios que no se pueden unir solos. No se subio nada."
  git push origin HEAD || parar "no se pudo subir"
  echo "Subido."
else
  echo "No se subio nada. Cuando quieras: git push"
fi
