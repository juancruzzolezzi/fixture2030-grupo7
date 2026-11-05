#!/usr/bin/env bash
# Hito 13 - Limpieza. Nunca toca los volumenes de las seis bases (RNF11).
#   bash scripts/limpiar_entorno.sh                 apaga el monitoreo, conserva sus metricas
#   bash scripts/limpiar_entorno.sh --comentarios   ademas borra los comentarios de la carga
#   bash scripts/limpiar_entorno.sh --metricas      ademas borra las metricas y Grafana (solo h13_*)
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_H10="../fixture2030-hito-10-api-integrada/.env"
BAJAR=(down)
for opcion in "$@"; do
  case "$opcion" in
    --comentarios)
      USUARIOS=""
      for i in $(seq -w 0 99); do USUARIOS="$USUARIOS'carga-h13-$i',"; done
      docker exec h10-cassandra cqlsh -e "DELETE FROM fixture2030.comentarios_por_bloque WHERE partido_id='F2030-006' AND bloque_horario='203006182355'; DELETE FROM fixture2030.comentarios_por_usuario WHERE usuario_id IN (${USUARIOS%,});"
      echo "Comentarios de la carga borrados (solo el bloque 203006182355 y los usuarios carga-h13-NN)." ;;
    --metricas) BAJAR=(down -v) ;;
    *) echo "opcion desconocida: $opcion"; exit 1 ;;
  esac
done
docker compose --env-file "$ENV_H10" --env-file .env "${BAJAR[@]}"
