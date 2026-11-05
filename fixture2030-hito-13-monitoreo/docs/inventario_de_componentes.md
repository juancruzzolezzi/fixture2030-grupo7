# Inventario de componentes

Regla que seguimos: una base figura como monitoreada solo si hay una métrica que lo respalde.
"Cómo se obtiene" distingue lo medido directamente, lo que viene de un exporter y lo que se
infiere (RNF3).

| Componente | Modelo | Función en el Fixture | Puerto o endpoint | Mecanismo | Métricas seleccionadas | Riesgo que se observa | Limitaciones del monitoreo |
|---|---|---|---|---|---|---|---|
| API integrada | - (HTTP) | Une los seis módulos | `:8000/metrics` | **Directo**: instrumentación propia | `api_http_requests_total`, `api_latency_seconds_bucket` | Saturación de la API, rutas lentas, 5xx | Sin CPU en Windows: `prometheus_client` solo publica métricas de proceso en Linux. Un solo proceso, sin vista por hilo. |
| MongoDB | Documental | Equipos y jugadores | `:9216/metrics` y API | **Exporter** + **directo** desde la API | `mongodb_up`, `mongodb_ss_opcounters`, `mongodb_ss_connections`, `mongodb_dbstats_*`, `database_up{database="mongodb"}` | Base caída, conexiones que crecen | El exporter entra con el usuario root del laboratorio. Un solo nodo: no hay métricas de réplica. |
| Redis | Clave-valor | Sesiones y caché | `:9121/metrics` y API | **Exporter** + **directo** desde la API | `redis_up`, `redis_memory_used_bytes`, `redis_memory_max_bytes`, `redis_commands_processed_total`, `redis_connected_clients`, `redis_evicted_keys_total` | Memoria llena, expulsión de sesiones y votos | Un solo nodo. Los hits y misses de la caché cuentan cualquier lectura, no solo las de la API. |
| Neo4j | Grafo | Partidos y eventos conectados | Solo vía API | **Directo** desde la API | `database_up`, `database_query_duration_seconds`, `database_errors_total`, con `database="neo4j"` | Base caída, recorridos lentos | **Sin vista interna**: memoria y caché del motor no se ven. La edición Community no trae endpoint de métricas para Prometheus. |
| Cassandra | Tabular | Comentarios masivos | Solo vía API | **Directo** desde la API | Las mismas, con `database="cassandra"`, y `comentarios_creados_total` | Base caída, escrituras lentas en un pico | **Sin vista interna**: tamaño de partición, compactación y carga por nodo no se ven. El exporter de la clase necesita un agente en la JVM; se propone para la siguiente iteración. |
| InfluxDB | Series temporales | Estadísticas en vivo | Solo vía API | **Directo** desde la API | Las mismas, con `database="influxdb"` | Base caída, ventanas lentas | **Sin vista interna**: la ingesta no pasa por la API, así que no se mide en este panel. |
| IRIS | Objetos | Entidad partido y su estado | Solo vía API | **Directo** desde la API | Las mismas, con `database="iris"` | Base caída, transiciones de estado que fallan | **Sin vista interna**. Un 409 por transición ilegal no cuenta como falla: es una regla de negocio funcionando. |
| Host Docker | - | Donde corren los contenedores | `:9100/metrics` | **Exporter** | `node_cpu_seconds_total`, `node_memory_MemAvailable_bytes` | CPU o memoria saturadas | En Docker Desktop mide la VM (WSL2), no Windows; la API corre afuera de esa VM. CPU por contenedor: no se mide acá (el Hito 12 usó `docker stats`). |
| Prometheus | Series temporales | Recolecta y evalúa alertas | `:9090/metrics` | **Directo** | `up`, `scrape_duration_seconds` | Quedarse sin datos sin darse cuenta | Si cae Prometheus, nadie avisa: no hay un segundo vigilante. |
| Grafana | - | Visualización | `:3000/api/health` | Se verifica con el script | - | - | No guarda datos: si cae, Prometheus sigue recolectando. |

## Qué significa `database_up` y qué no

`database_up` sale del chequeo de `/salud` de la API: ping en Redis, MongoDB y Neo4j, una lectura
mínima en Cassandra e InfluxDB y una llamada al Native SDK en IRIS. Nunca escribe (RNF5). Dice "la
API puede hablar con esa base". No dice que la base esté sana por dentro: para eso hacen falta las
métricas internas, que hoy solo tienen MongoDB y Redis.

Costo: una operación chica por base cada 15 s, que dispara el scrape. Antes de este hito las bases
solo recibían ese chequeo si alguien llamaba a `/salud`.

## Duración de los adaptadores

`database_query_duration_seconds` se mide alrededor de la función del adaptador: incluye el driver
y el cliente, además de la base. Se **infiere** que el tiempo está en la base solo si también lo
confirma otra señal. El Hito 12 es el ejemplo: el costo estaba en crear el cliente HTTP y no en
InfluxDB, que estaba casi ociosa.

## Exporters de la clase que no incorporamos

La Clase 14 muestra `neo4j-exporter:2000` y `cassandra-exporter:8080` como targets. No los
declaramos porque no los hicimos funcionar en el laboratorio, y la consigna no acepta una base
"monitoreada" solo en el diagrama. Queda como propuesta de instrumentación.
