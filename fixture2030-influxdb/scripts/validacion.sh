#!/usr/bin/env bash
# =============================================================================
# 4. VALIDACIÓN DE LA CARGA
# Compara lo que quedó en InfluxDB contra lo declarado por el generador
# (data/manifiesto.env): cantidad de puntos por tabla, cantidad de series,
# distribución por partido, tipos de los fields y consistencia entre fuentes.
# Solo usa SQL visto en clase (SELECT, DISTINCT, WHERE, GROUP BY, ORDER BY,
# COUNT, MIN, MAX). Los totales que combinan filas se calculan en bash.
# Uso: ./scripts/validacion.sh
# Salida: pantalla + docs/evidencia/03_validacion.txt
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/config.sh

RANGO="time >= '$TORNEO_INICIO' AND time < '$TORNEO_FIN'"

main() {
  encabezado "HITO 8 — VALIDACIÓN DE LA CARGA"
  verificar_contenedor
  cargar_token

  if [ ! -s "$MANIFIESTO" ]; then
    echo "ERROR: no existe $MANIFIESTO. Ejecutar primero la generación."; exit 1
  fi
  # shellcheck disable=SC1090
  source "$MANIFIESTO"
  echo "Estrategia declarada: PARTIDOS=$PARTIDOS DURACION_SEG=$DURACION_SEG INTERVALO_SEG=$INTERVALO_SEG"
  echo "Rango consultado: $TORNEO_INICIO a $TORNEO_FIN"

  echo
  echo "=== 1. CANTIDAD DE PUNTOS POR TABLA ==="
  comparar "Puntos en estadisticas" "$ESPERADO_ESTADISTICAS" \
    "$(valor_unico "SELECT COUNT(*) AS n FROM estadisticas WHERE $RANGO")"
  comparar "Puntos en audiencia" "$ESPERADO_AUDIENCIA" \
    "$(valor_unico "SELECT COUNT(*) AS n FROM audiencia WHERE $RANGO")"
  comparar "Puntos en eventos" "$ESPERADO_EVENTOS" \
    "$(valor_unico "SELECT COUNT(*) AS n FROM eventos WHERE $RANGO")"

  echo
  echo "=== 2. CANTIDAD DE SERIES (combinaciones distintas de tags) ==="
  comparar "Series en estadisticas (partido x equipo x sede)" "$ESPERADO_SERIES_ESTADISTICAS" \
    "$(contar_filas "SELECT DISTINCT partido_id, equipo_id, sede FROM estadisticas WHERE $RANGO")"
  comparar "Series en audiencia (partido x region)" "$ESPERADO_SERIES_AUDIENCIA" \
    "$(contar_filas "SELECT DISTINCT partido_id, region FROM audiencia WHERE $RANGO")"
  echo "Series en eventos (partido x equipo x tipo_evento), máximo teórico $(( PARTIDOS * 2 * 4 )): $(contar_filas "SELECT DISTINCT partido_id, equipo_id, tipo_evento FROM eventos WHERE $RANGO")"

  echo
  echo "=== 3. CONSISTENCIA ENTRE FUENTES ==="
  # Total de tiros según estadisticas: MAX(tiros) de cada equipo en cada partido, sumado en bash.
  local suma_max_tiros=0 _p _e m
  while IFS=, read -r _p _e m; do
    case "$m" in ''|*[!0-9]*) ;; *) suma_max_tiros=$(( suma_max_tiros + m )) ;; esac
  done < <(docker exec "$CONTAINER" influxdb3 query --database "$DATABASE" --token "$TOKEN" --format csv \
            "SELECT partido_id, equipo_id, MAX(tiros) AS max_tiros FROM estadisticas WHERE $RANGO GROUP BY partido_id, equipo_id" \
            2>/dev/null | tail -n +2 | tr -d '\r')
  comparar "Tiros según estadisticas (MAX por equipo, sumado)" "$ESPERADO_TIROS" "$suma_max_tiros"
  comparar "Tiros según eventos (COUNT de TIRO)" "$ESPERADO_TIROS" \
    "$(valor_unico "SELECT COUNT(*) AS n FROM eventos WHERE tipo_evento = 'TIRO' AND $RANGO")"
  comparar "Goles según eventos (COUNT de GOL)" "$ESPERADO_GOLES" \
    "$(valor_unico "SELECT COUNT(*) AS n FROM eventos WHERE tipo_evento = 'GOL' AND $RANGO")"

  consultar "4. Distribución de puntos por partido (estadisticas)" \
"SELECT partido_id, COUNT(*) AS puntos, MIN(time) AS primer_punto, MAX(time) AS ultimo_punto
FROM estadisticas
WHERE $RANGO
GROUP BY partido_id
ORDER BY partido_id"

  consultar "5. Tipos de los fields: primer segundo de M001 en estadisticas (float con decimal, enteros sin decimal)" \
"SELECT time, equipo_id, posesion_pct, pases_completados, tiros
FROM estadisticas
WHERE partido_id = 'M001' AND time = '2030-06-13T13:00:00Z'
ORDER BY equipo_id"

  consultar "5. Tipos de los fields: primer segundo de M001 en audiencia (entero)" \
"SELECT time, region, usuarios_conectados
FROM audiencia
WHERE partido_id = 'M001' AND time = '2030-06-13T13:00:00Z'
ORDER BY region"

  echo
  echo "=== RESULTADO ==="
  if [ "$ERRORES_VALIDACION" -eq 0 ]; then
    echo "VALIDACIÓN CORRECTA: la cantidad y distribución de puntos coincide con la estrategia declarada."
  else
    echo "VALIDACIÓN CON $ERRORES_VALIDACION DIFERENCIAS: revisar data/lotes_fallidos.txt y volver a cargar."
  fi
}

main "$@" 2>&1 | tee "$EVID_DIR/03_validacion.txt"
