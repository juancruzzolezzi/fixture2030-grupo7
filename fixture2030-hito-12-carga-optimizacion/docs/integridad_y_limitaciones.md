# Integridad y limitaciones

## Validación de integridad

Que la API conteste 201 no prueba que el comentario quedó guardado. Después de
cada corrida, `scripts/validar_integridad.py` lee Cassandra e InfluxDB
directamente y lo compara con lo que registró el generador. Resultado en
`evidencia/integridad_linea_base.txt` y `evidencia/integridad_optimizada.txt`.

| Verificación | Cómo |
|---|---|
| Escrituras aceptadas vs guardadas | Cada comentario de la corrida lleva una marca `[id-de-corrida]` en el contenido y una clave única. Se lee la partición `(F2030-006, 203006181900)` y se cruza con los ids que devolvió la API: faltantes, sobrantes y repetidos. |
| Rechazadas y sin respuesta | Se cuentan aparte. Una request que dio timeout pudo haberse escrito igual: si aparece en la tabla, se acepta como sobrante explicado. |
| Las dos tablas coinciden | La API escribe cada comentario en `comentarios_por_bloque` y en `comentarios_por_usuario`. Se compara el conjunto de ids de la corrida en ambas. |
| Datos sembrados intactos | Los 6.300 comentarios `[semilla]` siguen siendo 6.300, sin ids repetidos. Los puntos de InfluxDB siguen siendo 6.300 por equipo. |
| Contenido de las lecturas | Durante la carga, cada respuesta de lectura se valida: 20 comentarios, o 300 puntos ordenados por tiempo. Si no, cuenta como error `contenido_invalido`, aunque el status sea 200. |
| Reintentos | Al terminar la carga se mandan 3 comentarios dos veces cada uno con la misma `clave_idempotencia`, como un celular que reintenta porque no le llegó la respuesta. |

## Hallazgo: un reintento deja el comentario duplicado

La API del Hito 10 dice que reintentar con la misma clave no duplica
(RF19 del Hito 10). La validación muestra que **no se cumple**: el reintento
devuelve el mismo `comentario_id`, pero en la tabla quedan dos filas.

Causa: el id sale de la clave (`uuid5`), pero `creado_en` se toma con la hora
de cada request, y `creado_en` es parte de la clave primaria
(`PRIMARY KEY ((partido_id, bloque_horario), creado_en, comentario_id)`).
Dos requests con la misma clave escriben dos filas distintas.

Este hallazgo no depende de la optimización: aparece igual en la línea base y
en la corrida optimizada. La carga en sí no reintenta, por eso las
verificaciones de faltantes y repetidos de la corrida dan OK.

Arreglo propuesto, que no aplicamos en este hito: una tabla
`comentarios_por_clave` con clave `(partido_id, bloque_horario, clave)` y un
`INSERT ... IF NOT EXISTS`. El primer envío guarda su `creado_en`, y un
reintento lo lee y reutiliza, así escribe la misma fila. Tiene un costo: el
`IF NOT EXISTS` es una transacción liviana (Paxos), que en Cassandra son
varias idas y vueltas entre réplicas. La latencia de publicar subiría, y
habría que medirla con este mismo escenario antes de adoptarlo.

## Limitaciones

**Volumen probado vs proyectado (RNF6)**

| | Probado en la notebook | Proyectado para el Fixture |
|---|---|---|
| Comentarios en la base | 6.300 de un partido (300 por bloque) + los de cada corrida | Hito 6: 160.000 para F2030-006 y bloques calientes de hasta ~90.000 filas |
| Escrituras de comentarios | ~12/s (20 % de 60 ops/s) | Hito 6: picos de hasta 300 comentarios/s por partido |
| Puntos de estadísticas | 12.600 (un partido) | Hito 8: ~1,6 millones en la tabla `estadisticas` (127 partidos) |
| Usuarios simultáneos | 30 usuarios virtuales | Miles por partido |

- No extrapolamos latencias a esos volúmenes. Leer los últimos 20 comentarios
  de una partición de Cassandra no depende del tamaño de la partición, porque
  lee desde la punta del orden de clustering. Eso lo sabemos del modelo, no lo
  medimos con 90.000 filas.
- La consulta de estadísticas filtra por partido, equipo y 5 minutos. Con más
  partidos cargados, InfluxDB tendría más archivos para descartar. No lo
  medimos.

**Qué no pudimos medir**

- La capacidad máxima (a partir de qué tasa la API empieza a fallar o a
  atrasarse) en las dos versiones. Para eso habría que subir
  `USUARIOS_VIRTUALES` en `config/local.env` por escalones. Lo dejamos fuera
  para no exigir la notebook (RNF9).
- La red: todo corre en la misma máquina, así que la latencia de red es casi
  cero. En producción habría que sumarla.
- Disco y red de los contenedores. `docker stats` da CPU y memoria, que es lo
  que mostramos.

**Qué depende del entorno**

- Los milisegundos absolutos dependen de la notebook: CPU, Windows o Linux,
  memoria asignada a Docker. Por eso el entorno queda en el encabezado de cada
  resultado, y comparamos línea base y optimizada en la misma máquina, una
  después de la otra.
- Docker Desktop en Windows corre las bases dentro de una VM (WSL2), y la API
  y el generador corren afuera. Las dos corridas comparten esa misma
  situación.
- Entre la línea base y la optimizada la partición caliente tiene unos cientos
  de comentarios más, los escritos por la primera corrida. Las lecturas no los
  tocan: esos comentarios tienen fecha real (2026) y la lectura trae los 20 más
  nuevos del partido simulado (2030). La validación los separa por la marca de
  la corrida.

**Qué no se puede generalizar**

- Que la API "escala": es una medición a 60 ops/s con 30 usuarios, en una
  notebook, con datos de un partido.
- Que InfluxDB o Cassandra sean rápidos o lentos: el cuello de botella estaba
  en cómo la API usaba el cliente HTTP, no en la base.
