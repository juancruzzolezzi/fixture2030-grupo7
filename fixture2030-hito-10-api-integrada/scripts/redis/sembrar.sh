#!/usr/bin/env bash
# Datos de prueba minimos para el Hito 10, siguiendo la convencion de claves
# del Hito 7 (fixture2030:<dominio>:<id>). No reemplaza esa carga completa.
set -euo pipefail
CONTENEDOR="h10-redis"

docker exec "$CONTENEDOR" redis-cli HSET fixture2030:sesion:user-00001 \
  rol fan estado activa ultimo_acceso "2030-06-18T18:00:00Z" paginas_vistas 3 token tok-demo-no-real
docker exec "$CONTENEDOR" redis-cli EXPIRE fixture2030:sesion:user-00001 1800

docker exec "$CONTENEDOR" redis-cli SET fixture2030:cache:partido:F2030-006 \
  '{"codigo":"F2030-006","equipo_a":"ARG","equipo_b":"ESP","estado":"EnJuego"}' EX 60

echo "Redis sembrado: sesion de user-00001 y cache de F2030-006."
