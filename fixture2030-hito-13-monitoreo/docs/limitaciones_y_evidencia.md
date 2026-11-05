# Limitaciones y evidencia

Separamos cuatro cosas (RNF8). Si un número no tiene archivo o commit, no lo presentamos como medido.

## Medido

| Afirmación | Valor | Fuente | Entorno |
|---|---|---|---|
| Latencia de una request, sin carga | Mongo 5-6 ms, IRIS 5-6 ms, InfluxDB 25-27 ms | `hito-10/docs/evidencia/latencia.txt` | Notebook, 14/10/2026 |
| Carga línea base (30 usuarios, 60 ops/s pedidas) | 39,3 ops/s; p95 total 2.107 ms; CPU de API 556 %; 0 errores | `hito-12/docs/evidencia/resultados_linea_base.txt`, commit a6609bb | Windows 11, 8 CPU, 15,7 GB |
| Carga optimizada (mismo escenario) | 60,0 ops/s; p95 total 34,4 ms; CPU de API 23 %; 0 errores | `hito-12/docs/evidencia/resultados_optimizada.txt`, commit a6609bb | Igual |
| Integridad de escrituras | 807 aceptados, 807 en cada tabla, 0 faltantes | `hito-12/docs/evidencia/integridad_optimizada.txt` | Igual |
| Reintento duplica el comentario | 3 de 3 casos con 2 filas | El mismo archivo | Igual |
| Redis detenido | 503 en 0,19 s; `/equipos/ARG` sigue en 200; vuelve a 200 sin reiniciar la API | `hito-11/docs/evidencia/escenario_redis.txt` | Notebook |
| InfluxDB congelada | 504 en 3,0 s; vuelve a 200 | `hito-11/docs/evidencia/escenario_influxdb.txt` | Notebook |
| Ingesta en InfluxDB | 706.151 puntos, 9.945 puntos/s, 0 lotes fallidos | `fixture2030-influxdb/docs/evidencia/02_carga.txt` | Docker con 16 CPU |
| Targets, carga transversal y falla con Prometheus | Se completa con la corrida final | `evidencia/` de esta carpeta | Ver el encabezado de cada archivo |

## Objetivos de diseño (no son mediciones)

| Objetivo | Valor | De dónde sale |
|---|---|---|
| Picos de comentarios | Hasta 300/s por partido | Hito 6 |
| Comentarios de un partido de audiencia alta | ~160.000; bloque caliente de hasta ~90.000 | Hito 6 |
| Puntos en el torneo | ≈ 11,2 M | Hito 8 |
| Usuarios simultáneos | Miles por partido | Hito 12 |
| p95 < 100 ms | Umbral de la clase, no un compromiso con la FIFA | Clase 13 |

**Sin SLA**: definimos SLI (lo que medimos) y umbrales, pero no prometemos ningún SLO ante la FIFA,
porque no tenemos datos de un entorno real para sostenerlo.

## Estimaciones

| Estimación | Cómo se calculó | Por qué es solo eso |
|---|---|---|
| Cargar 11,2 M de puntos en ~19 min | 11.210.000 / 9.945 | Supone el mismo rendimiento a mayor volumen |
| Leer 20 comentarios no depende del tamaño de la partición | Por el modelo de clustering | No se midió con 90.000 filas |

## No se pudo obtener en el laboratorio

- **Capacidad máxima** de la versión optimizada: atiende 60 ops/s, no sabemos hasta dónde llega.
- **Varios nodos**: réplicas, conmutación, reparto de datos, caída de nodo o de región, CAP. Nada de esto se probó.
- **Red real**: todo corre en una máquina, con latencia casi nula.
- **Varios partidos simultáneos** y **volumen del torneo** a través de la API.
- **300 comentarios/s**: lo máximo medido son 10,9 escrituras/s, porque esa era la carga pedida.
- **Comparación contra una base relacional**: conceptual, no medida (`hito-12/docs/comparacion_relacional.md`).

## Limitaciones del monitoreo

Ver `inventario_de_componentes.md`. Las principales:

- Cuatro de las seis bases se ven solo desde la API.
- Sin notificación real de alertas (no hay Alertmanager).
- En Windows no hay CPU del proceso de la API en `/metrics`, y `node-exporter` mide la VM. Para CPU seguimos usando el método del Hito 12.
- Un intervalo de 15 s no ve un pico más corto; una caída se detecta entre 0 y unos 25 s (scrape más los 10 s del chequeo guardado).
- `histogram_quantile` estima entre límites de bucket: con la latencia en 34 ms, el valor cae entre 25 y 50 ms.
- La latencia del adaptador incluye el driver: no aísla a la base.

## Trazabilidad

Cada captura debe poder vincularse con su corrida: usar el rango que imprime
`ejecutar_prueba_controlada.py`, y nombrar el archivo como en `evidencia/LEEME.md`. La configuración
de cada panel está en `grafana/dashboards/fixture2030.json`; la de cada target, en `prometheus.yml`.

## Material que falta en el repositorio

Las carpetas de los Hitos 4, 5 y 6 (MongoDB, Neo4j, Cassandra) y los documentos de los Hitos 1 y 2 no
están en este repositorio. La defensa cita sus números a través de los Hitos 10 y 12. Hay que
subirlos antes de la defensa, porque una cifra del Hito 6 hoy no se puede verificar desde el repositorio.
