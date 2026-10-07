#!/usr/bin/env bash
# =============================================================================
# CONFIGURACIÓN COMPARTIDA — HITO 8 (Fixture 2030, series temporales)
# Lo cargan todos los scripts con: source scripts/config.sh
# No contiene secretos: el token vive solo en .influxdb3-token (excluido por .gitignore).
# =============================================================================

CONTAINER="fixture2030-influxdb"
DATABASE="fixture2030_series"
TOKEN_FILE=".influxdb3-token"
PRECISION="s"                       # precisión declarada para todas las escrituras

DATA_DIR="data"                     # datos generados (no se versionan)
ARCHIVO_LP="$DATA_DIR/puntos.lp"    # line protocol generado
MANIFIESTO="$DATA_DIR/manifiesto.env"
LOTES_DIR="$DATA_DIR/lotes"
EVID_DIR="docs/evidencia"

# Calendario simulado del torneo: 4 partidos por día desde el 13/06/2030.
# 1907539200 = 2030-06-13T00:00:00Z (epoch en segundos)
BASE_EPOCH=1907539200
TORNEO_INICIO="2030-06-13T00:00:00Z"
TORNEO_FIN="2030-07-16T00:00:00Z"

mkdir -p "$EVID_DIR"

encabezado() {
  echo "============================================================"
  echo "$1"
  echo "Fecha de ejecución: $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "Contenedor: $CONTAINER | Base: $DATABASE | Precisión: $PRECISION"
  echo "============================================================"
}

# Verificaciones tomadas del script de la Clase 9.
verificar_contenedor() {
  if ! docker ps --format '{{.Names}}' | grep -Fxq "$CONTAINER"; then
    echo "ERROR: el contenedor $CONTAINER no está en ejecución."
    echo "Revisar primero: docker compose logs influxdb"
    echo "Si el log muestra PermissionDenied en /var/lib/influxdb3/data, ejecutar:"
    echo "docker compose down && mkdir -p ~/docker/data/influxdb"
    echo "sudo chown -R \"\$(id -u):\$(id -g)\" ~/docker/data/influxdb && sudo chmod -R 777 ~/docker/data/influxdb"
    echo "docker compose up -d --force-recreate"
    exit 1
  fi
  if ! docker exec "$CONTAINER" influxdb3 --help >/dev/null 2>&1; then
    IMAGE="$(docker inspect "$CONTAINER" --format '{{.Config.Image}}' 2>/dev/null || true)"
    if [ "$IMAGE" != "influxdb:3-core" ]; then
      echo "ERROR: el contenedor no usa InfluxDB 3 Core. Imagen detectada: ${IMAGE:-desconocida}."
      echo "Ejecutar: docker compose down && docker compose pull && docker compose up -d --force-recreate"
    else
      echo "ERROR: el contenedor InfluxDB 3 Core no está listo. Revisar: docker compose logs influxdb"
    fi
    exit 1
  fi
  esperar_servidor
}

# Espera a que el servidor acepte conexiones (después de docker compose up -d tarda unos segundos).
esperar_servidor() {
  local i salida args=()
  if [ -s "$TOKEN_FILE" ]; then args=(--token "$(tr -d '\r\n' < "$TOKEN_FILE")"); fi
  for (( i = 1; i <= 60; i++ )); do
    salida="$(docker exec "$CONTAINER" influxdb3 show databases ${args[@]+"${args[@]}"} 2>&1 || true)"
    case "$salida" in
      *"(Connect)"*) ;;
      *) return 0 ;;
    esac
    [ "$i" -eq 1 ] && echo "Esperando a que InfluxDB termine de iniciar..."
    sleep 1
  done
  echo "ERROR: InfluxDB no respondió en 60 s. Revisar: docker compose logs influxdb"
  exit 1
}

cargar_token() {
  if [ ! -s "$TOKEN_FILE" ]; then
    echo "ERROR: no existe $TOKEN_FILE. Ejecutar primero ./scripts/inicializacion.sh"
    exit 1
  fi
  TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
  if [ -z "$TOKEN" ]; then
    echo "ERROR: el archivo $TOKEN_FILE está vacío."
    exit 1
  fi
}

# consultar "Título" "SQL"  -> muestra la consulta y el resultado en tabla
consultar() {
  echo
  echo "--- $1 ---"
  echo "SQL:"
  echo "$2" | sed 's/^/    /'
  echo "Resultado:"
  docker exec "$CONTAINER" influxdb3 query \
    --database "$DATABASE" \
    --token "$TOKEN" \
    "$2"
}

# valor_unico "SQL" -> devuelve solo el valor de una consulta de una fila y una columna
valor_unico() {
  docker exec "$CONTAINER" influxdb3 query \
    --database "$DATABASE" \
    --token "$TOKEN" \
    --format csv \
    "$1" 2>/dev/null | grep "[^[:space:]]" | tail -n 1 | tr -d '\r' || true
}

# contar_filas "SQL" -> cantidad de filas que devuelve una consulta (sin contar el encabezado)
contar_filas() {
  docker exec "$CONTAINER" influxdb3 query \
    --database "$DATABASE" \
    --token "$TOKEN" \
    --format csv \
    "$1" 2>/dev/null | tail -n +2 | grep -c . || true
}

# hora_partido MINUTOS -> instante ISO dentro de M001 (inicio 2030-06-13T13:00:00Z)
hora_partido() {
  printf '2030-06-13T%02d:%02d:00Z' $(( 13 + $1 / 60 )) $(( $1 % 60 ))
}

# comparar "Descripción" esperado observado -> imprime OK / DIFERENCIA y acumula errores
ERRORES_VALIDACION=0
comparar() {
  if [ "$2" = "$3" ]; then
    printf '[OK]         %-55s esperado=%-10s observado=%s\n' "$1" "$2" "$3"
  else
    printf '[DIFERENCIA] %-55s esperado=%-10s observado=%s\n' "$1" "$2" "$3"
    ERRORES_VALIDACION=$((ERRORES_VALIDACION + 1))
  fi
}
