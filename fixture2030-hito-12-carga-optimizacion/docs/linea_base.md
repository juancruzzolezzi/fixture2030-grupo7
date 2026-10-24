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

Lo que mostró en nuestras corridas, y lo que hay que verificar en cada una:

- **La tasa objetivo se alcanza** (60 ops/s, sin operaciones atrasadas ni
  errores). La API no está saturada al punto de rechazar, pero eso no quiere
  decir que esté bien: hay que mirar la latencia.
- **leer_estadisticas tiene un p95 varias veces mayor que las lecturas de
  comentarios**, aunque la consulta trae pocos datos. El p99 y el máximo
  muestran colas: algunas requests esperan mucho más que la mediana.
  Mirando solo el promedio no se vería.
- **La CPU de la API anda en un núcleo entero o más**, mientras InfluxDB
  casi no usa CPU. El generador queda bajo, así que no es él el que limita.
- **La evolución cada 5 s** muestra que el p95 sube con la rampa y se
  estabiliza en el sostenimiento. No hay degradación progresiva, así que
  60 s alcanzan para comparar.

Esa combinación (API ocupada, base tranquila, una sola ruta lenta) es la que
llevó a la hipótesis de `hipotesis_y_optimizacion.md`.

## Condiciones para que la comparación valga

- Mismo commit, misma configuración y misma máquina para la línea base y la
  optimizada. `comparar.py` lo verifica y lo deja escrito.
- Correr las dos una después de la otra, sin otros programas pesados
  abiertos.
- Las bases ya calientes. El calentamiento de 10 s no se compara, y la
  preparación de datos se hace antes de la línea base.
