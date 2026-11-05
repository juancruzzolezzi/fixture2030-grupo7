#!/usr/bin/env bash
# Hito 13 - Levanta Prometheus, Grafana y los exporters. Necesita las bases del Hito 10
# levantadas y la API en el puerto 8000 (README, pasos 1 y 2).
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_H10="../fixture2030-hito-10-api-integrada/.env"
[ -f "$ENV_H10" ] || { echo "ERROR: falta $ENV_H10 (ver el README del Hito 10)"; exit 1; }
[ -f .env ] || { echo "ERROR: falta .env: cp .env.example .env y poner una password"; exit 1; }
if grep -q "=CAMBIAR_" .env; then echo "ERROR: cambiar GRAFANA_PASSWORD en .env"; exit 1; fi
# Dos .env: la password de Grafana y el usuario de Mongo para su exporter. Ninguno se versiona.
docker compose --env-file "$ENV_H10" --env-file .env up -d
echo "Esperando a Prometheus y Grafana..."
for _ in $(seq 1 30); do
  if curl -fs -m 3 http://127.0.0.1:9090/-/healthy >/dev/null && curl -fs -m 3 http://127.0.0.1:3000/api/health >/dev/null; then
    echo "Prometheus: http://localhost:9090/targets"
    echo "Grafana:    http://localhost:3000/d/fixture2030 (usuario admin, password de .env)"
    exit 0
  fi
  sleep 2
done
echo "ERROR: no respondieron en 60 s. Revisar: docker compose logs prometheus grafana"; exit 1
