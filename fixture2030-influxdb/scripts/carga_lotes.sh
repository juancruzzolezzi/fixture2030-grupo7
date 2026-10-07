#!/usr/bin/env bash
# =============================================================================
# 3. CARGA EN LOTES (line protocol vía CLI influxdb3 write)
# - Divide data/puntos.lp en lotes de LOTE líneas
# - Escribe cada lote con: influxdb3 write --database ... --precision s
# - Reintenta cada lote hasta MAX_REINTENTOS veces ante error
# - Mide tiempo total y puntos por segundo observados en este equipo
#
# Concurrencia: 1 (lotes secuenciales). Ver docs/carga_y_consultas.md.
# Después de la carga, scripts/validacion.sh compara lo cargado con lo generado.
#
# Parámetros: LOTE=10000  MAX_REINTENTOS=3
# Uso: ./scripts/carga_lotes.sh
# Salida: pantalla + docs/evidencia/02_carga.txt
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/config.sh

LOTE="${LOTE:-10000}"
MAX_REINTENTOS="${MAX_REINTENTOS:-3}"

main() {
  encabezado "HITO 8 — CARGA EN LOTES MEDIANTE LINE PROTOCOL"
  verificar_contenedor
  cargar_token

  if [ ! -s "$ARCHIVO_LP" ]; then
    echo "ERROR: no existe $ARCHIVO_LP. Ejecutar primero ./scripts/generacion_puntos.sh"
    exit 1
  fi

  local total_lineas
  total_lineas=$(wc -l < "$ARCHIVO_LP" | tr -d ' ')

  rm -rf "$LOTES_DIR"
  mkdir -p "$LOTES_DIR"
  split -a 4 -l "$LOTE" "$ARCHIVO_LP" "$LOTES_DIR/lote_"

  local cantidad_lotes
  cantidad_lotes=$(ls "$LOTES_DIR" | wc -l | tr -d ' ')
  echo "Archivo:            $ARCHIVO_LP"
  echo "Puntos a cargar:    $total_lineas"
  echo "Tamaño de lote:     $LOTE líneas"
  echo "Cantidad de lotes:  $cantidad_lotes"
  echo "Concurrencia:       1 (secuencial)"
  echo "Reintentos máximos: $MAX_REINTENTOS por lote"
  echo

  local inicio=$SECONDS n=0 ok=0 fallidos=0 reintentos=0 archivo intento
  : > "$DATA_DIR/lotes_fallidos.txt"

  for archivo in "$LOTES_DIR"/lote_*; do
    n=$((n + 1))
    intento=1
    while true; do
      if docker exec -i "$CONTAINER" influxdb3 write \
           --database "$DATABASE" \
           --token "$TOKEN" \
           --precision "$PRECISION" < "$archivo" > /dev/null 2> "$DATA_DIR/ultimo_error.txt"; then
        ok=$((ok + 1))
        break
      fi
      if [ "$intento" -ge "$MAX_REINTENTOS" ]; then
        echo "  Lote $n ($(basename "$archivo")) FALLÓ tras $intento intentos: $(head -n 1 "$DATA_DIR/ultimo_error.txt")"
        echo "$archivo" >> "$DATA_DIR/lotes_fallidos.txt"
        fallidos=$((fallidos + 1))
        break
      fi
      echo "  Lote $n: error, reintento $intento de $MAX_REINTENTOS..."
      reintentos=$((reintentos + 1))
      intento=$((intento + 1))
      sleep 2
    done
    # Progreso cada 10 lotes y al final
    if [ $((n % 10)) -eq 0 ] || [ "$n" -eq "$cantidad_lotes" ]; then
      echo "  Progreso: $n / $cantidad_lotes lotes ($(( SECONDS - inicio )) s)"
    fi
  done

  local duracion=$(( SECONDS - inicio ))
  [ "$duracion" -lt 1 ] && duracion=1

  echo
  echo "=== RESULTADO DE LA CARGA ==="
  echo "Lotes escritos correctamente: $ok de $cantidad_lotes"
  echo "Lotes fallidos:               $fallidos (listados en $DATA_DIR/lotes_fallidos.txt)"
  echo "Reintentos realizados:        $reintentos"
  echo "Puntos enviados:              $total_lineas"
  echo "Tiempo total:                 $duracion s"
  echo "Rendimiento observado:        $(( total_lineas / duracion )) puntos/s (incluye el costo de docker exec por lote)"
  echo
  echo "Ambiente de la medición:"
  echo "  Versión InfluxDB: $(docker exec "$CONTAINER" influxdb3 --version 2>&1 | head -n 1)"
  echo "  Recursos Docker:  $(docker info --format '{{.NCPU}} CPU, {{.MemTotal}} bytes de RAM')"
  echo "  Sistema:          $(uname -sm)"
  echo
  if [ "$fallidos" -gt 0 ]; then
    echo "ATENCIÓN: hay lotes fallidos (ver $DATA_DIR/lotes_fallidos.txt). Revisar el error y comprobar con ./scripts/validacion.sh."
  fi
  echo "Carga finalizada. Siguiente paso: ./scripts/validacion.sh"
}

main "$@" 2>&1 | tee "$EVID_DIR/02_carga.txt"
