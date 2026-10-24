#!/usr/bin/env bash
# Hito 11 - Falla controlada de una dependencia y recuperacion.
#
#   bash scripts/escenario_falla.sh redis            # detiene Redis (docker compose stop) y lo vuelve a levantar
#   bash scripts/escenario_falla.sh influxdb pausar  # congela InfluxDB (docker compose pause): el puerto sigue abierto
#
# No borra volumenes ni datos: usa stop/start o pause/unpause sobre el compose
# del Hito 10. Necesita la API corriendo (bash scripts/iniciar_api.sh en el Hito 10).
# La salida queda en docs/evidencia/escenario_<servicio>.txt
set -uo pipefail

SERVICIO="${1:-redis}"
ACCION="${2:-detener}"
HITO11="$(cd "$(dirname "$0")/.." && pwd)"
HITO10="$HITO11/../fixture2030-hito-10-api-integrada"
API="${API_URL:-http://127.0.0.1:8000}"
ESPERA_MAX_S="${ESPERA_MAX_S:-120}"   # cuanto se espera, como mucho, a que la ruta vuelva a responder 200
# Ningun curl puede quedar colgado: 5 s para conectar y 20 s en total.
CURL=(curl -s --connect-timeout 5 --max-time 20)
SALIDA="$HITO11/docs/evidencia/escenario_${SERVICIO}.txt"

case "$SERVICIO" in
  redis)     RUTA="/sesiones/user-00001" ;;
  influxdb)  RUTA="/partidos/F2030-006/estadisticas?equipo_id=ARG&desde=2030-06-18T18:00:00Z&hasta=2030-06-18T18:05:00Z" ;;
  mongodb)   RUTA="/equipos/ARG" ;;
  neo4j)     RUTA="/partidos/F2030-006" ;;
  cassandra) RUTA="/partidos/F2030-006/comentarios?bloque_horario=203006181800" ;;
  iris)      RUTA="/partidos/F2030-006/entidad-compleja" ;;
  *) echo "servicio desconocido: $SERVICIO"; exit 1 ;;
esac
if [ "$ACCION" = "pausar" ]; then CAMBIO="pause"; VUELTA="unpause"; else CAMBIO="stop"; VUELTA="start"; fi

# Hace la request y muestra status, tiempo, request_id y el cuerpo (recortado).
# Los headers se leen de la misma salida de curl (-i): asi no hace falta un
# archivo temporal, que en Windows (Git Bash) no se encontraba.
pedir() {
  local salida ultima
  salida="$("${CURL[@]}" -i -w '\n%{http_code} %{time_total}' "$API$1" | tr -d '\r')"
  ultima="$(printf '%s\n' "$salida" | tail -n 1)"
  ULTIMO_ID="$(printf '%s\n' "$salida" | grep -i '^x-request-id' | cut -d' ' -f2)"
  echo "  GET $1"
  echo "    -> HTTP ${ultima% *} en ${ultima#* }s | request_id=${ULTIMO_ID:--}"
  echo "    -> $(printf '%s\n' "$salida" | tail -n 2 | head -n 1)" | cut -c1-200
}

compose() { (cd "$HITO10" && docker compose "$@"); }

# Version exacta que se probo: commit y, si los hay, archivos con cambios sin commitear.
COMMIT="$(git -C "$HITO11" rev-parse --short HEAD 2>/dev/null || echo desconocido)"
CAMBIOS="$(git -C "$HITO11/.." status --porcelain -- fixture2030-hito-10-api-integrada fixture2030-hito-11-conectividad/scripts 2>/dev/null | wc -l | tr -d ' ')"

{
  echo "Escenario de falla: $SERVICIO ($ACCION) | $(date -Iseconds)"
  echo "Commit: $COMMIT | archivos de la API o de los scripts sin commitear: $CAMBIOS"
  echo "API: $API"
  echo
  echo "== 1. Condicion inicial"
  echo "  contenedor: $(compose ps "$SERVICIO" --format '{{.Name}} {{.Status}}')"
  echo "  volumenes: $(docker inspect "h10-$SERVICIO" --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}} {{end}}{{end}}')"
  pedir "$RUTA"
  pedir "/salud?forzar=true"

  echo
  echo "== 2. Cambio aplicado: docker compose $CAMBIO $SERVICIO"
  compose "$CAMBIO" "$SERVICIO" 2>&1 | sed 's/^/  /'

  echo
  echo "== 3. Durante la falla"
  pedir "$RUTA"
  ID_FALLA="$ULTIMO_ID"
  pedir "/salud?forzar=true"
  pedir "/salud/listo"
  echo "  otro modulo (deberia seguir andando):"
  if [ "$SERVICIO" = "mongodb" ]; then pedir "/partidos/F2030-006"; else pedir "/equipos/ARG"; fi
  echo "  log de la API para esa request (request_id=${ID_FALLA:--}):"
  if [ -n "$ID_FALLA" ]; then
    grep "$ID_FALLA" "$HITO10/api.log" 2>/dev/null | sed 's/^.*fixture2030.api /    /' | cut -c1-250
  fi

  echo
  echo "== 4. Recuperacion: docker compose $VUELTA $SERVICIO"
  compose "$VUELTA" "$SERVICIO" 2>&1 | sed 's/^/  /'
  INICIO=$(date +%s)
  RECUPERADO=no
  while [ $(( $(date +%s) - INICIO )) -lt "$ESPERA_MAX_S" ]; do
    if [ "$("${CURL[@]}" -o /dev/null -w '%{http_code}' "$API$RUTA")" = "200" ]; then RECUPERADO=si; break; fi
    sleep 2
  done
  if [ "$RECUPERADO" = si ]; then
    echo "  la ruta volvio a responder 200 a los $(( $(date +%s) - INICIO )) s"
  else
    echo "  ATENCION: la ruta NO volvio a responder 200 en ${ESPERA_MAX_S} s (revisar docker compose ps y el log de la API)"
  fi

  echo
  echo "== 5. Despues de recuperar"
  pedir "$RUTA"
  pedir "/salud?forzar=true"
  echo "  volumenes: $(docker inspect "h10-$SERVICIO" --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}} {{end}}{{end}}')"
} 2>&1 | tee "$SALIDA"

echo
echo "-> $SALIDA"
# Codigo de salida distinto de 0 si la dependencia no se recupero
! grep -q "NO volvio a responder 200" "$SALIDA"
