#!/usr/bin/env bash
# Carga datos de prueba minimos en las seis fuentes, para poder probar la API
# de punta a punta. No reemplaza la evidencia de volumen de cada hito: esto
# es una muestra chica y reproducible, pensada solo para este modulo de
# integracion (RNF11).
set -euo pipefail
cd "$(dirname "$0")/.."
# Git Bash (Windows) convierte rutas como /dev/stdin en rutas de Windows; esto lo evita.
export MSYS_NO_PATHCONV=1

# Usuarios y passwords salen del .env (no se versiona). tr: por si tiene fin de linea de Windows.
[ -f .env ] || { echo "ERROR: falta .env (cp .env.example .env y completar las passwords)"; exit 1; }
if grep -q "=CAMBIAR_" .env; then echo "ERROR: completar las passwords CAMBIAR_... del .env"; exit 1; fi
set -a; source <(tr -d '\r' < .env); set +a

echo "=== MongoDB ==="
docker exec h10-mongodb mongosh --quiet --eval "db.runCommand({ping:1})" >/dev/null
# En Windows el comando suele ser "python" y el venv usa Scripts/ en vez de bin/.
if python3 --version >/dev/null 2>&1; then PYTHON=python3; else PYTHON=python; fi
[ -d .venv_seed ] || "$PYTHON" -m venv .venv_seed
if [ -x .venv_seed/bin/python ]; then SEED_PY=.venv_seed/bin/python; else SEED_PY=.venv_seed/Scripts/python.exe; fi
"$SEED_PY" -m pip install -q pymongo >/dev/null
"$SEED_PY" scripts/mongo/generate_and_load.py

echo
echo "=== Neo4j ==="
# La password se toma adentro del contenedor (NEO4J_AUTH), no pasa por esta linea de comandos.
docker exec -i h10-neo4j sh -c 'cypher-shell -u neo4j -p "${NEO4J_AUTH#neo4j/}" --file /dev/stdin' < scripts/neo4j/sembrar.cypher

echo
echo "=== Cassandra ==="
docker exec -i h10-cassandra cqlsh < scripts/cassandra/esquema.cql
docker exec -i h10-cassandra cqlsh < scripts/cassandra/carga_muestra.cql

echo
echo "=== Redis ==="
bash scripts/redis/sembrar.sh

echo
echo "=== InfluxDB ==="
bash scripts/influxdb/sembrar.sh
# El token queda en .env para la API (no se muestra en pantalla).
sed -i "s|^INFLUX_TOKEN=.*|INFLUX_TOKEN=$(tr -d '\r\n' < .influxdb3-token)|" .env
echo "Token de InfluxDB copiado a .env."

echo
echo "=== IRIS ==="
# Le pone a _SYSTEM la password del .env (en vez de la que trae la imagen) y evita
# el "Password change required" del primer login por el puerto 1972. La password
# viaja como variable de entorno, no como argumento visible.
IRIS_NUEVA_PASSWORD="$IRIS_PASSWORD" docker exec -i -e IRIS_NUEVA_PASSWORD h10-iris iris session IRIS -U %SYS < scripts/iris/preparar_login.txt
docker exec -i h10-iris iris session IRIS -U USER < scripts/iris/compilar.txt
docker exec -i h10-iris iris session IRIS -U USER < scripts/iris/sembrar.txt

echo
echo "Datos de prueba cargados en las seis fuentes."
