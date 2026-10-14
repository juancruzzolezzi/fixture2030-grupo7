#!/usr/bin/env bash
# Carga datos de prueba minimos en las seis fuentes, para poder probar la API
# de punta a punta. No reemplaza la evidencia de volumen de cada hito: esto
# es una muestra chica y reproducible, pensada solo para este modulo de
# integracion (RNF11).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== MongoDB ==="
docker exec -i h10-mongodb mongosh --quiet "mongodb://fixture_admin:fixture2030@localhost:27017/fixture2030?authSource=admin" <<'EOF' >/dev/null
db.runCommand({ping:1})
EOF
python3 -m venv .venv_seed >/dev/null 2>&1 || true
source .venv_seed/bin/activate
pip install -q pymongo >/dev/null
MONGO_URI="mongodb://fixture_admin:fixture2030@localhost:27017/?authSource=admin" python3 scripts/mongo/generate_and_load.py
deactivate

echo
echo "=== Neo4j ==="
docker exec -i h10-neo4j cypher-shell -u neo4j -p fixture2030_local --file /dev/stdin < scripts/neo4j/sembrar.cypher

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

echo
echo "=== IRIS ==="
# La imagen Community exige cambiar la contraseña de _SYSTEM en el primer
# login real (no en la terminal local, que usa confianza del SO). Sin este
# paso, el Native SDK de Python falla con "Password change required" al
# conectar por el puerto 1972. Se hace una sola vez; repetirlo no molesta.
docker exec -i h10-iris iris session IRIS -U %SYS < scripts/iris/preparar_login.txt
docker exec -i h10-iris iris session IRIS -U USER < scripts/iris/compilar.txt
docker exec -i h10-iris iris session IRIS -U USER < scripts/iris/sembrar.txt

echo
echo "Datos de prueba cargados en las seis fuentes."
