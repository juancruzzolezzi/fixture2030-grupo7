#!/usr/bin/env bash
# =============================================================================
# 1. INICIALIZACIÓN Y AUTORIZACIÓN LOCAL
# - Verifica el contenedor InfluxDB 3 Core (mismas comprobaciones de la Clase 9)
# - Registra versión, imagen y recursos del ambiente (RNF10)
# - Crea el token de administración la primera vez y lo guarda en .influxdb3-token
# - Crea las bases con la politica de retencion de docs/retencion_y_granularidad.md
#   (correccion de la devolucion: antes la base del laboratorio quedaba sin vencimiento)
# Uso: ./scripts/inicializacion.sh   (desde la carpeta del módulo)
# Salida: pantalla + docs/evidencia/00_inicializacion.txt
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/config.sh

main() {
  encabezado "HITO 8 — INICIALIZACIÓN DEL AMBIENTE"
  verificar_contenedor

  echo
  echo "=== 1. AMBIENTE OBSERVADO ==="
  echo "Imagen declarada: $(docker inspect "$CONTAINER" --format '{{.Config.Image}}')"
  echo "ID de imagen:     $(docker inspect "$CONTAINER" --format '{{.Image}}')"
  echo "Versión InfluxDB: $(docker exec "$CONTAINER" influxdb3 --version 2>&1 | head -n 1)"
  echo "Docker (motor):   $(docker info --format '{{.ServerVersion}}')"
  echo "Recursos Docker:  $(docker info --format '{{.NCPU}} CPU, {{.MemTotal}} bytes de RAM')"
  echo "Sistema:          $(uname -sm)"
  echo "Persistencia:     $HOME/docker/data/influxdb -> /var/lib/influxdb3/data"
  echo
  docker compose ps

  echo
  echo "=== 2. AUTORIZACIÓN LOCAL (TOKEN) ==="
  if [ ! -s "$TOKEN_FILE" ]; then
    echo "Creando el primer token de administración local..."
    if ! SALIDA="$(docker exec "$CONTAINER" influxdb3 create token --admin 2>&1)"; then
      echo "ERROR: no se pudo crear el token de administración."
      echo "$SALIDA"
      echo
      echo "Si la instancia ya tiene un token de administración (por ejemplo, de la demo de la Clase 9),"
      echo "copiar el archivo .influxdb3-token de esa carpeta a esta carpeta y volver a ejecutar."
      echo "Si ese token se perdió: detener Compose, borrar ~/docker/data/influxdb y empezar de cero (ver README)."
      exit 1
    fi
    # La salida puede incluir texto además del token: se conserva solo el valor del token.
    TOKEN_NUEVO="$(printf '%s\n' "$SALIDA" | grep -o 'apiv3_[A-Za-z0-9_-]*' | head -n 1 || true)"
    if [ -z "$TOKEN_NUEVO" ]; then
      TOKEN_NUEVO="$(printf '%s' "$SALIDA" | tr -d '\r\n')"
    fi
    (umask 077; printf '%s\n' "$TOKEN_NUEVO" > "$TOKEN_FILE")
    echo "Token guardado en $TOKEN_FILE (permiso 600, excluido por .gitignore, no se muestra)."
  else
    echo "Se reutiliza el token existente en $TOKEN_FILE (no se muestra)."
  fi
  cargar_token

  echo
  echo "=== 3. BASES DE DATOS DEL MÓDULO (CON RETENCIÓN) ==="
  # Datos crudos: torneo + 15 días ≈ 50 días. Si la base ya existía sin retención
  # (corridas anteriores a la corrección), se actualiza: InfluxDB 3 Core 3.x admite
  # `update database --retention-period` (verificado con la 3.12.1).
  if ! docker exec "$CONTAINER" influxdb3 show databases --token "$TOKEN" --format json | grep -Fq "\"$DATABASE\""; then
    echo "Creando la base $DATABASE con retención $RETENCION_CRUDOS..."
    docker exec "$CONTAINER" influxdb3 create database --token "$TOKEN" --retention-period "$RETENCION_CRUDOS" "$DATABASE"
  else
    echo "La base $DATABASE ya existe; se aplica la retención $RETENCION_CRUDOS."
    docker exec "$CONTAINER" influxdb3 update database --token "$TOKEN" --database "$DATABASE" --retention-period "$RETENCION_CRUDOS"
  fi
  # Resúmenes históricos: sin vencimiento (se crea vacía; la llenan las consultas de ventana AG2).
  if ! docker exec "$CONTAINER" influxdb3 show databases --token "$TOKEN" --format json | grep -Fq "\"$DATABASE_HISTORICO\""; then
    docker exec "$CONTAINER" influxdb3 create database --token "$TOKEN" "$DATABASE_HISTORICO"
  fi

  echo
  echo "Retención configurada (system.databases, retention_period_ns -> días):"
  docker exec "$CONTAINER" influxdb3 query --database _internal --token "$TOKEN" \
    "SELECT database_name, retention_period_ns / 86400000000000 AS retencion_dias FROM system.databases WHERE database_name IN ('$DATABASE', '$DATABASE_HISTORICO')"

  echo
  echo "=== 4. VERIFICACIÓN DEL SERVIDOR ==="
  docker exec "$CONTAINER" influxdb3 show databases --token "$TOKEN"
  echo
  echo "Inicialización finalizada."
}

main "$@" 2>&1 | tee "$EVID_DIR/00_inicializacion.txt"
