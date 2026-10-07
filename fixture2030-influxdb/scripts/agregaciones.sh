#!/usr/bin/env bash
# =============================================================================
# 6. AGREGACIONES Y RESÚMENES TEMPORALES
# La función de agregación se elige según el significado de cada medida
# (tabla "La operación define el agregado correcto" de la Clase 9):
#   posesion_pct         -> muestra            -> AVG
#   pases / tiros        -> contador acumulado -> MAX (sumar lecturas duplica)
#   usuarios_conectados  -> estado medido      -> MAX / MIN / AVG según objetivo
#   eventos              -> evento individual  -> COUNT
# Solo usa SQL visto en clase. Las ventanas temporales se arman como
# consultas acotadas por rango (WHERE time >= inicio AND time < fin).
# Uso: ./scripts/agregaciones.sh
# Salida: pantalla + docs/evidencia/05_agregaciones.txt
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/config.sh

main() {
  encabezado "HITO 8 — AGREGACIONES Y RESÚMENES TEMPORALES"
  verificar_contenedor
  cargar_token

  consultar "AG1. Resumen por equipo en M001 (incluye SUM(tiros) para mostrar por qué es incorrecto)" \
"SELECT equipo_id,
       AVG(posesion_pct) AS posesion_promedio,
       MAX(pases_completados) AS pases_totales,
       MAX(tiros) AS tiros_totales,
       SUM(tiros) AS suma_incorrecta_de_tiros
FROM estadisticas
WHERE partido_id = 'M001'
  AND time >= '2030-06-13T13:00:00Z' AND time < '2030-06-13T14:45:00Z'
GROUP BY equipo_id
ORDER BY equipo_id"

  echo
  echo "--- AG2. Downsampling: ventanas de 5 minutos para ARG en M001 (6.300 puntos -> 21 filas) ---"
  echo "Cada ventana es la misma consulta acotada a un rango de 5 minutos:"
  echo "    SELECT AVG(posesion_pct) AS posesion_promedio,"
  echo "           MAX(pases_completados) AS pases_acumulados,"
  echo "           MAX(tiros) AS tiros_acumulados,"
  echo "           COUNT(*) AS puntos_resumidos"
  echo "    FROM estadisticas"
  echo "    WHERE partido_id = 'M001' AND equipo_id = 'ARG'"
  echo "      AND time >= '<inicio de ventana>' AND time < '<fin de ventana>'"
  echo "Resultado:"
  printf '%-22s %-8s %s\n' "ventana_inicio" "minutos" "posesion_promedio,pases_acumulados,tiros_acumulados,puntos_resumidos"
  local m ini fin fila total_resumido=0
  for (( m = 0; m < 105; m += 5 )); do
    ini=$(hora_partido "$m")
    fin=$(hora_partido $(( m + 5 )))
    fila=$(valor_unico "SELECT AVG(posesion_pct) AS posesion_promedio,
       MAX(pases_completados) AS pases_acumulados,
       MAX(tiros) AS tiros_acumulados,
       COUNT(*) AS puntos_resumidos
FROM estadisticas
WHERE partido_id = 'M001' AND equipo_id = 'ARG'
  AND time >= '$ini' AND time < '$fin'")
    printf '%-22s %-8s %s\n' "$ini" "$(( m + 1 ))-$(( m + 5 ))" "$fila"
    case "${fila##*,}" in
      ''|*[!0-9]*) ;;
      *) total_resumido=$(( total_resumido + ${fila##*,} )) ;;
    esac
  done
  echo "Total de puntos resumidos en las 21 ventanas: $total_resumido"

  consultar "AG3. Conteo de eventos por tipo y equipo en M001" \
"SELECT equipo_id, tipo_evento, COUNT(*) AS cantidad
FROM eventos
WHERE partido_id = 'M001'
  AND time >= '2030-06-13T13:00:00Z' AND time < '2030-06-13T14:45:00Z'
GROUP BY equipo_id, tipo_evento
ORDER BY equipo_id, tipo_evento"

  consultar "AG4. Torneo: los 5 partidos con más tiros (eventos TIRO)" \
"SELECT partido_id, COUNT(*) AS tiros
FROM eventos
WHERE tipo_evento = 'TIRO'
  AND time >= '$TORNEO_INICIO' AND time < '$TORNEO_FIN'
GROUP BY partido_id
ORDER BY tiros DESC, partido_id
LIMIT 5"

  consultar "AG5. Torneo: pico, mínimo y promedio de usuarios conectados por partido (todas las regiones)" \
"SELECT partido_id,
       MAX(usuarios_conectados) AS pico_regional,
       MIN(usuarios_conectados) AS minimo_regional,
       AVG(usuarios_conectados) AS promedio_regional
FROM audiencia
WHERE time >= '$TORNEO_INICIO' AND time < '$TORNEO_FIN'
GROUP BY partido_id
ORDER BY pico_regional DESC"

  echo
  echo "Agregaciones finalizadas."
}

main "$@" 2>&1 | tee "$EVID_DIR/05_agregaciones.txt"
