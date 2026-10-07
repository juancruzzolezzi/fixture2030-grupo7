#!/usr/bin/env bash
# =============================================================================
# 7. LIMPIEZA OPCIONAL
# Borra solo los archivos generados localmente (data/). No toca InfluxDB.
# Reiniciar toda la instancia es una acción intencional y manual (Clase 9):
#   docker compose down
#   rm -rf ~/docker/data/influxdb   (puede requerir sudo)
#   rm -f .influxdb3-token
#   y volver a preparar la carpeta y ejecutar docker compose up -d
# Uso: ./scripts/limpieza.sh
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/config.sh

echo "Borrando archivos generados en $DATA_DIR/ ..."
rm -rf "$DATA_DIR"
echo "Listo. Los datos cargados en InfluxDB y el token NO se modificaron."
echo
echo "Para reiniciar toda la instancia (borra los datos de InfluxDB), ejecutar a mano:"
echo "  docker compose down"
echo "  sudo rm -rf ~/docker/data/influxdb && rm -f $TOKEN_FILE"
echo "  mkdir -p ~/docker/data/influxdb"
echo "  sudo chown -R \"\$(id -u):\$(id -g)\" ~/docker/data/influxdb && sudo chmod -R 777 ~/docker/data/influxdb"
echo "  docker compose up -d"
