# Datos de prueba

Los genera `scripts/preparar_datos.py`. Son sintéticos (no hay datos reales
ni personales), con semilla fija (`2030`): correrlo dos veces escribe
exactamente lo mismo, sin duplicar.

## Dónde van

- Cassandra: keyspace `fixture2030_h12`, con el esquema del Hito 6 leído de
  `fixture2030-hito-10-api-integrada/scripts/cassandra/esquema.cql`. Solo
  cambia el nombre del keyspace.
- InfluxDB: base `fixture2030_h12`, tabla `estadisticas` con los mismos tags y
  fields del Hito 8.

Los datos del Hito 10 (`fixture2030` y `fixture2030_series`) no se tocan.

## Qué se carga

| | Cantidad | Distribución |
|---|---|---|
| Partido | 1: `F2030-006` (ARG vs ESP, sede BUE), 18/06/2030 18:00 UTC, 105 min | El mismo código que en las otras bases |
| Comentarios | 6.300 = 21 bloques de 5 min × 300 | Hora al azar dentro de cada bloque. 2.000 hinchas posibles con peso 1/rango^0,8: unos pocos comentan mucho y la mayoría poco. Likes con distribución exponencial. Texto de una lista de 10 frases, con la marca `[semilla]`. |
| Estadísticas | 12.600 puntos = 6.300 s × 2 equipos | 1 muestra por segundo por equipo, como en el Hito 8. La posesión de ARG es una caminata al azar entre 30 % y 70 %, y la de ESP es el complemento. Pases y tiros son contadores acumulados que solo crecen. |

## Claves calientes

En la prueba de carga, el 80 % de las lecturas de comentarios y todas las
escrituras van al bloque `203006181900` (minuto 60). Las estadísticas se piden
siempre para la misma ventana (18:55 a 19:00). Así se representa lo que pasa
en un partido en vivo: todo el mundo mira lo último.

## Validación de la carga

Después de escribir, el script lee de vuelta:

- los comentarios `[semilla]` de las 21 particiones (tienen que ser 6.300);
- `COUNT(*)` por equipo en InfluxDB (tienen que ser 6.300 cada uno).

Lo deja en `docs/evidencia/preparacion_datos.txt` con `[OK]` o `[FALLA]`.

## Relación con el volumen proyectado

Es un partido, no el torneo. El Hito 6 cargó 160.000 comentarios solo para
F2030-006, y el Hito 8 proyecta 1,6 millones de puntos de estadísticas para
los 127 partidos. Acá cargamos lo necesario para que las lecturas de la
prueba tengan datos reales que devolver. Qué cambiaría con más volumen está en
`docs/integridad_y_limitaciones.md`.

`COMENTARIOS_POR_BLOQUE` se puede subir en `config/local.env` para probar con
particiones más grandes.
