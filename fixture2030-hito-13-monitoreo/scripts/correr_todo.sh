#!/usr/bin/env bash
# Hito 13 - Corre todo el hito de punta a punta en la notebook (lo lanza correr_hito13.bat).
# Levanta las bases, la API y el monitoreo, commitea, genera la evidencia y pregunta antes de subir.
# No borra volumenes ni detiene contenedores de otros proyectos. Se puede volver a correr.
set -uo pipefail
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
H10="$RAIZ/fixture2030-hito-10-api-integrada"
H13="$RAIZ/fixture2030-hito-13-monitoreo"
REPO_URL="${REPO_URL:-https://github.com/juancruzzolezzi/fixture2030-grupo7.git}"
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
mkdir -p "$H13/trabajo"
exec > >(tee -a "$H13/trabajo/corrida.log") 2>&1
parar() { echo; echo "SE DETUVO: $1"; echo "Detalle: fixture2030-hito-13-monitoreo/trabajo/corrida.log"; exit 1; }
paso() { echo; echo "=== $1 ($(date +%H:%M:%S))"; }
cd "$RAIZ" || exit 1

paso "1/8 Repositorio"
git --version >/dev/null 2>&1 || parar "falta Git"
if [ ! -d .git ]; then
  # El zip se descomprimio en una carpeta nueva: se trae el repo sin pisar los archivos del zip.
  git init -q && git remote add origin "$REPO_URL" && git fetch -q origin main || parar "no se pudo traer el repo de GitHub"
  git reset -q origin/main && git branch -qM main && git branch -q --set-upstream-to=origin/main main
  git ls-files -d -z | xargs -0 -r git checkout -q --
fi
git remote get-url origin 2>/dev/null | grep -qi "fixture2030-grupo7" || parar "esta carpeta no es el repo fixture2030-grupo7"
[ -n "$(git config user.email)" ] || parar "falta configurar Git: git config --global user.name y user.email"

paso "2/8 Docker"
if ! docker info >/dev/null 2>&1; then
  echo "Abriendo Docker Desktop..."
  "${LOCALAPPDATA:-}/Programs/DockerDesktop/Docker Desktop.exe" >/dev/null 2>&1 &
  "${PROGRAMFILES:-}/Docker/Docker/Docker Desktop.exe" >/dev/null 2>&1 &
  for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 5; done
fi
docker info >/dev/null 2>&1 || parar "Docker no responde. Abri Docker Desktop y volve a correrlo."

for p in 27017 7474 7687 9042 6379 8181 1972 52773 9090 3000 9100 9121 9216; do
  otro="$(docker ps --format '{{.Names}} {{.Ports}}' | grep -E "[:]$p->" | grep -vE '^(h10-|fixture2030-)' | cut -d' ' -f1)"
  [ -z "$otro" ] || parar "el contenedor '$otro' ocupa el puerto $p. Detenelo (docker stop $otro) y volve a correr esto."
done

paso "3/8 Configuracion (passwords generadas, no se muestran ni se versionan)"
if [ ! -f "$H10/.env" ]; then
  if docker volume ls -q | grep -q "fixture2030-hito-10-api-integrada_h10_mongo_data" || docker ps -a --format '{{.Names}}' | grep -q '^h10-'; then
    parar "ya hay bases del Hito 10 con otras passwords. Descomprimi el zip en la copia del repo que tiene su .env."
  fi
fi
python_ok() { "$@" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >/dev/null 2>&1; }
if python_ok py -3.12; then PYBASE=(py -3.12); elif python_ok python; then PYBASE=(python); elif python_ok python3; then PYBASE=(python3); else parar "falta Python 3.10 o superior"; fi
# Rutas relativas: con MSYS_NO_PATHCONV, el Python de Windows no entiende /c/Users/...
"${PYBASE[@]}" - fixture2030-hito-10-api-integrada fixture2030-hito-13-monitoreo <<'PY'
import pathlib, secrets, sys
h10, h13 = map(pathlib.Path, sys.argv[1:])
def completar(destino, ejemplo):
    texto = destino.read_text(encoding="utf-8") if destino.exists() else ejemplo.read_text(encoding="utf-8")
    lineas = [l.split("=")[0] + "=lab" + secrets.token_hex(12) if "=CAMBIAR_" in l else l for l in texto.splitlines()]
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
completar(h10 / ".env", h10 / ".env.example")
completar(h13 / ".env", h13 / ".env.example")
PY
[ -f "$H10/.env" ] && [ -f "$H13/.env" ] || parar "no se pudieron crear los .env"

paso "4/8 Bases del Hito 10 (la primera vez descarga varios GB)"
cd "$H10" || exit 1
docker compose up -d || parar "no levantaron las bases"
for _ in $(seq 1 90); do
  faltan=""
  for c in h10-mongodb h10-neo4j h10-cassandra h10-redis; do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$c" 2>/dev/null)" = "healthy" ] || faltan="$faltan $c"
  done
  [ -z "$faltan" ] && break
  echo "  esperando:$faltan"; sleep 10
done
[ -z "$faltan" ] || parar "no quedaron healthy:$faltan"

sembradas=no
if grep -q '^INFLUX_TOKEN=.\+' .env && docker exec h10-cassandra cqlsh -e "SELECT partido_id FROM fixture2030.comentarios_por_bloque LIMIT 1" 2>/dev/null | grep -q "F2030"; then sembradas=si; fi
if [ "$sembradas" = no ]; then
  echo "Sembrando datos de laboratorio..."
  sleep 20  # InfluxDB e IRIS no tienen healthcheck en el compose
  bash scripts/sembrar_datos.sh || parar "fallo la siembra de datos"
fi

paso "5/8 API con metricas"
if [ -f .venv/Scripts/python.exe ]; then PY="$PWD/.venv/Scripts/python.exe"; elif [ -f .venv/bin/python ]; then PY="$PWD/.venv/bin/python"; else
  "${PYBASE[@]}" -m venv .venv || parar "no se pudo crear el venv"
  if [ -f .venv/Scripts/python.exe ]; then PY="$PWD/.venv/Scripts/python.exe"; else PY="$PWD/.venv/bin/python"; fi
fi
"$PY" -m pip install -q --only-binary=:all: -r requirements.txt || parar "no se instalaron las dependencias"
"$PY" -m pip install -q playwright py-spy || echo "AVISO: sin Playwright no habra capturas automaticas"
# Siempre una API nueva: asi corre el codigo de este commit, aunque haya quedado otra colgada.
if command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*uvicorn*app.main:app*--port 8000*' } | ForEach-Object { taskkill /F /T /PID \$_.ProcessId }" >/dev/null 2>&1
else
  pkill -f 'uvicorn app.main:app.*--port 8000' 2>/dev/null
fi
sleep 2
echo "Si Windows pregunta por el firewall para Python, hay que tocar Permitir."
nohup bash scripts/iniciar_api.sh >/dev/null 2>&1 &
for _ in $(seq 1 30); do curl -fs -m 2 http://127.0.0.1:8000/salud/vivo >/dev/null && break; sleep 2; done
curl -fs -m 15 http://127.0.0.1:8000/metrics >/dev/null || parar "la API no expone /metrics"

paso "6/8 Commit del codigo (la evidencia queda vinculada a este commit)"
cd "$RAIZ" || exit 1
git add fixture2030-hito-10-api-integrada
# La evidencia va en su propio commit, y solo si la corrida se completa.
git reset -q
git add fixture2030-hito-10-api-integrada
git add -- fixture2030-hito-13-monitoreo ':(exclude)fixture2030-hito-13-monitoreo/evidencia/*'
if ! git diff --cached --quiet; then git commit -q -m "Hito 13: monitoreo con Prometheus y Grafana, y material de la defensa" || parar "fallo el commit"; fi
git log -1 --format='%h %s'

paso "7/8 Monitoreo y evidencia (~8 min, no cierres esta ventana)"
cd "$H13" || exit 1
bash scripts/iniciar_monitoreo.sh || parar "no levanto el monitoreo"
"$PY" scripts/generar_evidencia.py; EVIDENCIA_OK=$?
if [ "$EVIDENCIA_OK" != 0 ] && ! curl -fs -m 10 http://127.0.0.1:8000/metrics >/dev/null && command -v powershell.exe >/dev/null 2>&1; then
  # La API quedo trabada: se guarda en que parte del codigo, para poder diagnosticarlo.
  (cd "$H10" && powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Where-Object { \$_.CommandLine -like '*spawn_main*' } | ForEach-Object { .\\.venv\\Scripts\\py-spy.exe dump --pid \$_.ProcessId }") > "$H13/trabajo/api_trabada.txt" 2>&1
  echo "La API quedo trabada. Diagnostico en fixture2030-hito-13-monitoreo/trabajo/api_trabada.txt"
fi
[ "$EVIDENCIA_OK" = 0 ] || parar "la evidencia quedo incompleta; no se commiteo ni se subio. Revisar la salida de arriba."

paso "8/8 Commit de la evidencia"
cd "$RAIZ" || exit 1
git add fixture2030-hito-13-monitoreo
if ! git diff --cached --quiet; then git commit -q -m "Hito 13: evidencia de targets, carga, falla controlada y capturas" || parar "fallo el commit de la evidencia"; fi
git log -2 --format='%h %s'
echo
echo "Evidencia lista en fixture2030-hito-13-monitoreo/evidencia/"
echo "Grafana: http://localhost:3000/d/fixture2030  (usuario admin, password en fixture2030-hito-13-monitoreo/.env)"
read -r -p "Subir estos commits a GitHub (rama $(git rev-parse --abbrev-ref HEAD))? [s/N] " RESPUESTA
if [ "$RESPUESTA" = "s" ] || [ "$RESPUESTA" = "S" ]; then
  git pull -q --ff-only origin "$(git rev-parse --abbrev-ref HEAD)" || parar "el remoto tiene cambios que no se pueden unir solos. No se subio nada."
  git push origin HEAD || parar "no se pudo subir"
  echo "Subido."
else
  echo "No se subio nada. Cuando quieras: git push"
fi
echo "Todo sigue corriendo. Para apagar el monitoreo: bash fixture2030-hito-13-monitoreo/scripts/limpiar_entorno.sh"
