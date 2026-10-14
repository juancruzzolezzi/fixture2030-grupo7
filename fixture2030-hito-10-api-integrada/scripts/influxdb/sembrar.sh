#!/usr/bin/env bash
# Token local + base + un puñado de puntos, siguiendo el modelo del Hito 8
# (measurement `estadisticas`: tags partido_id/equipo_id/sede, fields
# posesion_pct float, pases_completados/tiros enteros). Usa los mismos
# codigos F2030-xxx que Mongo/Neo4j/Cassandra para este hito de integracion.
set -euo pipefail
cd "$(dirname "$0")/../.."
CONTENEDOR="h10-influxdb"
DATABASE="fixture2030_series"
TOKEN_FILE=".influxdb3-token"

if [ ! -s "$TOKEN_FILE" ]; then
  SALIDA="$(docker exec "$CONTENEDOR" influxdb3 create token --admin 2>&1)"
  TOKEN="$(printf '%s\n' "$SALIDA" | grep -o 'apiv3_[A-Za-z0-9_-]*' | head -n 1)"
  (umask 077; printf '%s\n' "$TOKEN" > "$TOKEN_FILE")
else
  TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
fi

docker exec "$CONTENEDOR" influxdb3 create database --token "$TOKEN" "$DATABASE" 2>&1 | grep -v "already exists" || true

# influxdb3 write solo acepta UNA linea de protocolo por invocacion (probado
# contra el contenedor real: con varios argumentos posicionales rechaza con
# "ensure that a single protocol line string is provided"). Se escribe una
# llamada por punto.
# Epochs = 2030-06-18T18:0{0,1,2,3,4}:00Z (coincide con bloque_horario
# "203006181800" usado en Mongo/Neo4j/Cassandra para este mismo hito).
PUNTOS=(
  "estadisticas,partido_id=F2030-006,equipo_id=ARG,sede=BUE posesion_pct=52.3,pases_completados=10i,tiros=1i 1908036000"
  "estadisticas,partido_id=F2030-006,equipo_id=ARG,sede=BUE posesion_pct=54.1,pases_completados=25i,tiros=2i 1908036060"
  "estadisticas,partido_id=F2030-006,equipo_id=ARG,sede=BUE posesion_pct=55.0,pases_completados=40i,tiros=3i 1908036120"
  "estadisticas,partido_id=F2030-006,equipo_id=ESP,sede=BUE posesion_pct=47.7,pases_completados=30i,tiros=1i 1908036000"
  "estadisticas,partido_id=F2030-006,equipo_id=ESP,sede=BUE posesion_pct=45.9,pases_completados=50i,tiros=2i 1908036060"
)
for punto in "${PUNTOS[@]}"; do
  docker exec "$CONTENEDOR" influxdb3 write --database "$DATABASE" --token "$TOKEN" "$punto"
done

echo "InfluxDB sembrado: 5 puntos de 'estadisticas' para F2030-006 (ARG/ESP)."
