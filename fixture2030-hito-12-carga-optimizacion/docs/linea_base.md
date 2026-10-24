# Línea base

La línea base es la API tal como quedó en el Hito 10 (`INFLUX_REUSAR_CLIENTE=0`)
bajo el escenario de `flujo_y_escenario_de_carga.md`. Se corre con
`bash scripts/ejecutar_linea_base.sh` y queda en:

| Archivo | Qué tiene |
|---|---|
| `evidencia/preparacion_datos.txt` | Datos cargados y verificados de vuelta (6.300 comentarios, 12.600 puntos) |
| `evidencia/prueba_hipotesis.txt` | Prueba aislada del cliente HTTP (ver `hipotesis_y_optimizacion.md`) |
| `evidencia/resultados_linea_base.txt` | Resumen legible |
| `evidencia/resultados_linea_base.json` | Lo mismo, completo: cada muestra de recursos y la evolución cada 5 s |
| `evidencia/integridad_linea_base.txt` | Verificación contra las bases |

## Qué queda registrado (sección 5.4 de la consigna)

| Pedido | Dónde está en el resultado |
|---|---|
| Commit o versión del código | Encabezado `commit:`. Si algún archivo de la API o de los scripts no estaba commiteado, aparece la lista. Por eso commiteamos los scripts **antes** de correr. |
| Configuración de la API y productos | `INFLUX_REUSAR_CLIENTE`, keyspace, base de InfluxDB, puerto, timeout. El resto de la configuración de la API es el `.env` del Hito 10 (sin secretos en la evidencia). |
| Versión de imágenes y clientes | Línea `Imagenes:` (imagen y versión de Cassandra e InfluxDB, leídas con `docker inspect`) y `Entorno:` (Python, fastapi, uvicorn, httpx, cassandra-driver) |
| Cantidad y distribución de datos | Línea `Datos:` + `preparacion_datos.txt` |
| Duración y concurrencia | Línea `Escenario:` |
| Latencia mínima, promedio y percentiles | Tabla por operación y fase (`min`, `p50`, `p90`, `p95`, `p99`, `max`; el promedio está en el .json) |
| Throughput | Columna `ok/s` y línea "Tasa objetivo / lograda" |
| Tasa y tipos de error | Columna `err` y línea `errores:` |
| CPU, memoria | Sección "Recursos": API, generador y los dos contenedores |
| Registros recibidos, aceptados y rechazados | Línea `Escrituras:` + `integridad_linea_base.txt` |
| Estabilidad | Tabla "Evolución cada 5 s" |

## Cómo leer la línea base

Nuestra corrida: `li1023230127-1e4d`, 23/10/2026, Windows 11, 8 CPU
lógicas, 15,7 GB de RAM, commit a6609bb sin cambios pendientes. Cassandra
5.0.9 e InfluxDB 3.12.1.

- **La API no alcanza la tasa pedida**: logra 39,3 de 60 ops/s, y 579
  operaciones salieron tarde porque la anterior no había respondido. No hubo
  errores (ninguna request llegó al timeout de 10 s), pero la API estaba
  saturada: atendía todo, lento.
- **leer_estadisticas es la que tarda**: mediana 1.681 ms, p95 2.767 ms y
  máximo 3.290 ms, para una consulta de 300 puntos. Las lecturas de
  comentarios tienen mediana 21 ms y p95 34 ms. El p99 de publicar (90 ms,
  contra una mediana de 34 ms) muestra que también hay colas en las rutas de
  comentarios, pero chicas al lado de las estadísticas.
- **La CPU de la API promedia 556 %** (más de 5 núcleos de 8), mientras
  InfluxDB usa 9 %. El generador promedia 15 %, con un pico de 69 % en una
  muestra. No es él el que limita: si lo fuera, la API estaría ociosa.
- **La evolución cada 5 s**: en el sostenimiento el p95 oscila entre 1,5 y
  2,8 s y las ops/s entre 33 y 45, sin una tendencia a empeorar. Es una
  saturación estable, no una degradación progresiva, así que 60 s alcanzan
  para comparar.

Esa combinación (API ocupada, base tranquila, una sola ruta lenta) es la que
llevó a la hipótesis de `hipotesis_y_optimizacion.md`.

## Condiciones para que la comparación valga

- Mismo commit, misma configuración y misma máquina para la línea base y la
  optimizada. `comparar.py` lo verifica y lo deja escrito.
- Correr las dos una después de la otra, sin otros programas pesados
  abiertos.
- Las bases ya calientes. El calentamiento de 10 s no se compara, y la
  preparación de datos se hace antes de la línea base.
