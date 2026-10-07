#!/usr/bin/env bash
# =============================================================================
# 2. GENERACIÓN DE PUNTOS (line protocol)
# Simula las estadísticas en vivo de los partidos del Fixture 2030 y escribe
# un archivo de line protocol. No se conecta a InfluxDB: generación y carga
# están separadas (RF7).
#
# Tablas generadas (ver docs/modelo_multidimensional.md):
#   estadisticas : 1 punto por equipo y por segundo  (muestra + contadores acumulados)
#   audiencia    : 1 punto por región y por segundo   (estado medido: usuarios conectados)
#   eventos      : 1 punto por evento individual       (TIRO, GOL, FALTA, CORNER)
#
# Parámetros (variables de entorno, con valores por defecto para la prueba local):
#   PARTIDOS=8        cantidad de partidos a generar (1 a 127)
#   DURACION_SEG=6300 duración de cada partido en segundos (105 min con adicionado)
#   INTERVALO_SEG=1   cada cuántos segundos se toma una muestra
#
# Objetivo de diseño (10M+): PARTIDOS=127 -> 11.201.400 puntos de estadisticas + audiencia.
# Uso: PARTIDOS=8 ./scripts/generacion_puntos.sh
# Salida: data/puntos.lp, data/manifiesto.env y docs/evidencia/01_generacion.txt
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/config.sh

PARTIDOS="${PARTIDOS:-8}"
DURACION_SEG="${DURACION_SEG:-6300}"
INTERVALO_SEG="${INTERVALO_SEG:-1}"

# 64 selecciones (formato de 127 partidos usado en la materia). El orden define los cruces.
EQUIPOS=(ARG POR MAR ESP URU PAR BRA FRA GER ENG ITA NED BEL CRO SUI DEN
         POL SRB AUT SWE NOR SCO WAL CZE UKR TUR GRE SEN NGA EGY TUN ALG
         CMR GHA CIV RSA MLI JPN KOR AUS IRN KSA QAT IRQ UZB JOR CHN UAE
         NZL MEX USA CAN CRC PAN JAM HON SLV GUA COL ECU CHI PER VEN BOL)
SEDES=(Buenos_Aires Rabat Montevideo Asuncion Madrid Lisboa)
REGIONES=(AMERICA_SUR AMERICA_CENTRAL AMERICA_NORTE CARIBE EUROPA_OESTE EUROPA_ESTE
          EUROPA_NORTE AFRICA_NORTE AFRICA_SUBSAHARIANA MEDIO_ORIENTE ASIA OCEANIA)

main() {
  encabezado "HITO 8 — GENERACIÓN DE PUNTOS EN LINE PROTOCOL"

  if [ "$PARTIDOS" -lt 1 ] || [ "$PARTIDOS" -gt 127 ]; then
    echo "ERROR: PARTIDOS debe estar entre 1 y 127."; exit 1
  fi
  if [ "${#EQUIPOS[@]}" -ne 64 ]; then
    echo "ERROR: la lista de equipos debe tener 64 códigos (tiene ${#EQUIPOS[@]})."; exit 1
  fi

  mkdir -p "$DATA_DIR"
  local muestras=$(( (DURACION_SEG + INTERVALO_SEG - 1) / INTERVALO_SEG ))
  local esperado_est=$(( PARTIDOS * 2 * muestras ))
  local esperado_aud=$(( PARTIDOS * ${#REGIONES[@]} * muestras ))
  local total_eventos=0 total_tiros=0 total_goles=0
  local inicio_gen=$SECONDS

  echo "Parámetros: PARTIDOS=$PARTIDOS DURACION_SEG=$DURACION_SEG INTERVALO_SEG=$INTERVALO_SEG"
  echo "Muestras por serie: $muestras"
  echo "Generando $ARCHIVO_LP ..."

  : > "$ARCHIVO_LP"
  local k
  for (( k = 1; k <= PARTIDOS; k++ )); do
    local pid dia slot inicio j r loc vis sede
    pid=$(printf 'M%03d' "$k")
    dia=$(( (k - 1) / 4 )); slot=$(( (k - 1) % 4 ))
    inicio=$(( BASE_EPOCH + dia * 86400 + (13 + slot * 3) * 3600 ))   # 13, 16, 19 y 22 h UTC
    j=$(( (k - 1) % 32 )); r=$(( (k - 1) / 32 ))
    loc=${EQUIPOS[$(( 2 * j ))]}
    vis=${EQUIPOS[$(( (2 * j + 1 + 2 * r) % 64 ))]}
    sede=${SEDES[$(( (k - 1) % ${#SEDES[@]} ))]}

    RANDOM=$(( 2030 + k ))          # semilla fija por partido: mismos datos en cada ejecución
    local p=500                     # posesión del local en décimas (500 = 50.0 %)
    local pases_l=0 pases_v=0 tiros_l=0 tiros_v=0
    local usuarios=() g
    for (( g = 0; g < ${#REGIONES[@]}; g++ )); do usuarios[g]=$(( 20000 + RANDOM )); done

    local s ts minuto ev_partido=0
    for (( s = 0; s < DURACION_SEG; s += INTERVALO_SEG )); do
      ts=$(( inicio + s ))
      minuto=$(( s / 60 + 1 ))

      # Posesión: paseo aleatorio acotado entre 30 % y 70 %; el visitante es el complemento.
      p=$(( p + RANDOM % 11 - 5 ))
      (( p < 300 )) && p=300
      (( p > 700 )) && p=700
      # Pases completados: contador acumulado; la probabilidad depende de la posesión.
      (( RANDOM % 1000 < p / 6 )) && pases_l=$(( pases_l + 1 ))
      (( RANDOM % 1000 < (1000 - p) / 6 )) && pases_v=$(( pases_v + 1 ))

      # Eventos individuales por equipo. Un TIRO incrementa el contador acumulado de tiros.
      local idx eq rr gol=0
      for idx in 0 1; do
        if (( idx == 0 )); then eq=$loc; else eq=$vis; fi
        rr=$(( RANDOM % 1000 ))
        if (( rr < 2 )); then
          if (( idx == 0 )); then tiros_l=$(( tiros_l + 1 )); else tiros_v=$(( tiros_v + 1 )); fi
          printf 'eventos,partido_id=%s,equipo_id=%s,tipo_evento=TIRO minuto=%di,dorsal=%di %d\n' \
            "$pid" "$eq" "$minuto" $(( RANDOM % 26 + 1 )) "$ts"
          ev_partido=$(( ev_partido + 1 )); total_tiros=$(( total_tiros + 1 ))
          if (( RANDOM % 10 == 0 )); then
            printf 'eventos,partido_id=%s,equipo_id=%s,tipo_evento=GOL minuto=%di,dorsal=%di %d\n' \
              "$pid" "$eq" "$minuto" $(( RANDOM % 26 + 1 )) "$ts"
            ev_partido=$(( ev_partido + 1 )); total_goles=$(( total_goles + 1 )); gol=1
          fi
        elif (( rr < 4 )); then
          printf 'eventos,partido_id=%s,equipo_id=%s,tipo_evento=FALTA minuto=%di,dorsal=%di %d\n' \
            "$pid" "$eq" "$minuto" $(( RANDOM % 26 + 1 )) "$ts"
          ev_partido=$(( ev_partido + 1 ))
        elif (( rr < 5 )); then
          printf 'eventos,partido_id=%s,equipo_id=%s,tipo_evento=CORNER minuto=%di,dorsal=%di %d\n' \
            "$pid" "$eq" "$minuto" $(( RANDOM % 26 + 1 )) "$ts"
          ev_partido=$(( ev_partido + 1 ))
        fi
      done

      # Estadísticas por equipo (posesion_pct float; pases y tiros enteros con sufijo i).
      printf 'estadisticas,partido_id=%s,equipo_id=%s,sede=%s posesion_pct=%d.%d,pases_completados=%di,tiros=%di %d\n' \
        "$pid" "$loc" "$sede" $(( p / 10 )) $(( p % 10 )) "$pases_l" "$tiros_l" "$ts"
      printf 'estadisticas,partido_id=%s,equipo_id=%s,sede=%s posesion_pct=%d.%d,pases_completados=%di,tiros=%di %d\n' \
        "$pid" "$vis" "$sede" $(( (1000 - p) / 10 )) $(( (1000 - p) % 10 )) "$pases_v" "$tiros_v" "$ts"

      # Audiencia por región: estado medido. Un gol produce un salto de conexiones.
      for (( g = 0; g < ${#REGIONES[@]}; g++ )); do
        usuarios[g]=$(( usuarios[g] + RANDOM % 201 - 100 + gol * 3000 ))
        (( usuarios[g] < 0 )) && usuarios[g]=0
        printf 'audiencia,partido_id=%s,region=%s usuarios_conectados=%di %d\n' \
          "$pid" "${REGIONES[g]}" "${usuarios[g]}" "$ts"
      done
    done >> "$ARCHIVO_LP"

    total_eventos=$(( total_eventos + ev_partido ))
    printf '  %s  %s vs %s  sede=%-12s  inicio_epoch=%d  eventos=%d\n' \
      "$pid" "$loc" "$vis" "$sede" "$inicio" "$ev_partido"
  done

  local lineas
  lineas=$(wc -l < "$ARCHIVO_LP" | tr -d ' ')

  cat > "$MANIFIESTO" <<EOF
# Generado por scripts/generacion_puntos.sh — usado por scripts/validacion.sh
PARTIDOS=$PARTIDOS
DURACION_SEG=$DURACION_SEG
INTERVALO_SEG=$INTERVALO_SEG
MUESTRAS_POR_SERIE=$muestras
ESPERADO_ESTADISTICAS=$esperado_est
ESPERADO_AUDIENCIA=$esperado_aud
ESPERADO_EVENTOS=$total_eventos
ESPERADO_TIROS=$total_tiros
ESPERADO_GOLES=$total_goles
ESPERADO_SERIES_ESTADISTICAS=$(( PARTIDOS * 2 ))
ESPERADO_SERIES_AUDIENCIA=$(( PARTIDOS * ${#REGIONES[@]} ))
LINEAS_TOTALES=$lineas
EOF

  echo
  echo "Resumen de la generación:"
  echo "  estadisticas : $esperado_est puntos"
  echo "  audiencia    : $esperado_aud puntos"
  echo "  eventos      : $total_eventos puntos ($total_tiros tiros, $total_goles goles)"
  echo "  TOTAL        : $lineas líneas de line protocol"
  echo "  Tamaño       : $(du -h "$ARCHIVO_LP" | cut -f1)"
  echo "  Tiempo de generación: $(( SECONDS - inicio_gen )) s"
  echo
  echo "Primeras líneas del archivo:"
  head -n 5 "$ARCHIVO_LP"
  echo
  echo "Generación finalizada. Siguiente paso: ./scripts/carga_lotes.sh"
}

main "$@" 2>&1 | tee "$EVID_DIR/01_generacion.txt"
