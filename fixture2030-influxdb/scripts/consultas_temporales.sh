#!/usr/bin/env bash
# =============================================================================
# 5. CONSULTAS TEMPORALES (SQL sobre InfluxDB 3 Core)
# Cada consulta responde un patrón de acceso de docs/patrones_de_acceso.md
# y siempre acota rango temporal y dimensiones (RNF8).
# Solo usa SQL visto en clase: SELECT, WHERE, AND, GROUP BY, ORDER BY (DESC),
# LIMIT, AVG, MIN, MAX, COUNT y alias con AS.
#
# Partido de referencia: M001 ARG vs POR, sede Buenos_Aires.
#   Inicio: 2030-06-13T13:00:00Z (minuto 1)  Fin: 2030-06-13T14:45:00Z (105 min)
#   Minuto 60 = 14:00:00Z, minuto 75 = 14:15:00Z
# Uso: ./scripts/consultas_temporales.sh
# Salida: pantalla + docs/evidencia/04_consultas.txt
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/config.sh

main() {
  encabezado "HITO 8 — CONSULTAS TEMPORALES"
  verificar_contenedor
  cargar_token

  consultar "PA1. Ventana temporal: evolución de ARG en M001 entre el minuto 60 y el 75 (primeros 10 puntos)" \
"SELECT time, equipo_id, posesion_pct, pases_completados, tiros
FROM estadisticas
WHERE partido_id = 'M001' AND equipo_id = 'ARG'
  AND time >= '2030-06-13T14:00:00Z' AND time < '2030-06-13T14:15:00Z'
ORDER BY time
LIMIT 10"

  consultar "PA1. Evolución entre el minuto 60 y el 75: cantidad de puntos y valores de la ventana (900 puntos esperados)" \
"SELECT equipo_id,
       COUNT(*) AS puntos_en_ventana,
       MIN(posesion_pct) AS posesion_minima,
       MAX(posesion_pct) AS posesion_maxima,
       MIN(tiros) AS tiros_al_minuto_60,
       MAX(tiros) AS tiros_al_minuto_75
FROM estadisticas
WHERE partido_id = 'M001' AND equipo_id = 'ARG'
  AND time >= '2030-06-13T14:00:00Z' AND time < '2030-06-13T14:15:00Z'
GROUP BY equipo_id"

  consultar "PA2. Pantalla en vivo: último estado de cada equipo en M001 (último minuto)" \
"SELECT time, equipo_id, posesion_pct, pases_completados, tiros
FROM estadisticas
WHERE partido_id = 'M001'
  AND time >= '2030-06-13T14:44:00Z' AND time < '2030-06-13T14:45:00Z'
ORDER BY time DESC, equipo_id
LIMIT 2"

  consultar "PA3. Comparación entre equipos: posesión promedio en los últimos 5 minutos de M001" \
"SELECT equipo_id,
       AVG(posesion_pct) AS posesion_promedio,
       MIN(posesion_pct) AS posesion_minima,
       MAX(posesion_pct) AS posesion_maxima
FROM estadisticas
WHERE partido_id = 'M001'
  AND time >= '2030-06-13T14:40:00Z' AND time < '2030-06-13T14:45:00Z'
GROUP BY equipo_id
ORDER BY equipo_id"

  consultar "PA4. Filtro por sede: partidos jugados en Buenos_Aires durante el torneo" \
"SELECT partido_id, equipo_id,
       MIN(time) AS inicio, MAX(time) AS fin, COUNT(*) AS puntos
FROM estadisticas
WHERE sede = 'Buenos_Aires'
  AND time >= '$TORNEO_INICIO' AND time < '$TORNEO_FIN'
GROUP BY partido_id, equipo_id
ORDER BY partido_id, equipo_id"

  consultar "PA5. Comparación entre fuentes: pico de usuarios conectados por región en M001" \
"SELECT region,
       MAX(usuarios_conectados) AS pico_usuarios,
       MIN(usuarios_conectados) AS minimo_usuarios,
       AVG(usuarios_conectados) AS promedio_usuarios
FROM audiencia
WHERE partido_id = 'M001'
  AND time >= '2030-06-13T13:00:00Z' AND time < '2030-06-13T14:45:00Z'
GROUP BY region
ORDER BY pico_usuarios DESC"

  consultar "PA6. Eventos individuales de M001 (goles), ordenados por tiempo" \
"SELECT time, equipo_id, tipo_evento, minuto, dorsal
FROM eventos
WHERE partido_id = 'M001' AND tipo_evento = 'GOL'
  AND time >= '2030-06-13T13:00:00Z' AND time < '2030-06-13T14:45:00Z'
ORDER BY time"

  echo
  echo "Consultas finalizadas. Siguiente paso: ./scripts/agregaciones.sh"
}

main "$@" 2>&1 | tee "$EVID_DIR/04_consultas.txt"
