# Alertas y umbrales

Las reglas están en `prometheus/reglas-o-alertas.yml` y se ven en http://localhost:9090/alerts.

**Límite**: Prometheus las evalúa y muestra su estado, pero no hay Alertmanager ni notificación.
En una operación real, ese aviso le llegaría a la guardia. Quién la atiende está indicado como rol:
no tenemos una guardia real.

Los umbrales de latencia y errores son los de la Clase 13. Son **experimentales**: los contrastamos
con lo que medimos en el Hito 12, no con el tráfico de un torneo.

## Disponibilidad

### `BaseDeDatosCaida`

| | |
|---|---|
| Métrica | `database_up` |
| Condición | `database_up == 0` |
| Duración mínima | 1 minuto |
| Severidad | critical |
| Componente | La base de la etiqueta `database` |
| Impacto en el Fixture | Depende de la base. Redis: sesiones. Cassandra: comentarios. InfluxDB: estadísticas. IRIS: control del partido. Neo4j: partido y eventos. MongoDB: fichas. Los demás módulos siguen. |
| Quién atiende | Operación de datos |
| Investigación y recuperación | `docker compose ps` y `logs` de esa base en el Hito 10; `GET /salud?forzar=true`; `docker compose start <base>`. No borrar volúmenes. |
| Por qué ese umbral | 1 minuto son al menos 4 scrapes: evita avisar por un chequeo perdido. Con cuatro lecturas seguidas ya no parece ruido. En un partido en vivo se podría bajar. |

### `ApiFixtureCaida`

| | |
|---|---|
| Métrica | `up{job="fixture-api"}` |
| Condición | `== 0` |
| Duración mínima | 1 minuto |
| Severidad | critical |
| Componente | API integrada |
| Impacto en el Fixture | Ninguna pantalla puede consultar datos, aunque las bases estén bien |
| Quién atiende | Operación de la plataforma |
| Investigación y recuperación | `curl http://localhost:8000/salud/vivo`, `api.log`; si responde desde la notebook, revisar firewall (README). Reiniciar la API. |
| Por qué ese umbral | Mismo criterio que `BaseDeDatosCaida`. |

### `ExporterCaido`

| | |
|---|---|
| Métrica | `up{capa="infraestructura"}` |
| Condición | `== 0` |
| Duración mínima | 2 minutos |
| Severidad | warning |
| Componente | El exporter de la etiqueta `job` |
| Impacto en el Fixture | Ninguno directo: se pierde la vista de esa infraestructura y se puede pasar por alto otro problema |
| Quién atiende | Operación de monitoreo |
| Investigación y recuperación | `docker compose ps` y `logs` del exporter en esta carpeta. Comparar con `database_up` antes de suponer que la base cayó. |
| Por qué ese umbral | No afecta al usuario: se tolera más tiempo que una base caída. |

## Rendimiento

### `ApiLatenciaP95Alta`

| | |
|---|---|
| Métrica | `api_latency_seconds_bucket` |
| Condición | p95 por ruta en 5 min `> 0,1 s` |
| Duración mínima | 2 minutos |
| Severidad | warning |
| Componente | API, ruta de la etiqueta `ruta` |
| Impacto en el Fixture | La pantalla de esa ruta se siente lenta. Si sigue subiendo, la API se atrasa y baja el throughput, como en la línea base del Hito 12. |
| Quién atiende | Equipo de la API |
| Investigación y recuperación | Panel "API contra adaptadores". Si solo sube la API: CPU y cola. Si sube el adaptador: esa base o su cliente. |
| Por qué ese umbral | Es el de la Clase 13 y separa bien lo medido en el Hito 12: p95 total de 34 ms con la versión optimizada y de 2.107 ms con la saturada. |

### `BaseLatenciaP95Alta`

| | |
|---|---|
| Métrica | `database_query_duration_seconds_bucket` |
| Condición | p95 por base en 5 min `> 0,1 s` |
| Duración mínima | 2 minutos |
| Severidad | warning |
| Componente | Adaptador de la etiqueta `database` |
| Impacto en el Fixture | El módulo de esa base responde más lento, aunque sin errores todavía |
| Quién atiende | Operación de datos |
| Investigación y recuperación | Mirar si es una sola operación; `docker stats`; en Cassandra, si el bloque es el caliente; en InfluxDB, si la ventana pedida es acotada. |
| Por qué ese umbral | Clase 13. Las lecturas medidas en el Hito 10 están entre 5 y 25 ms, así que 100 ms ya es anormal. Es experimental. |

### `ApiErroresAltos`

| | |
|---|---|
| Métrica | `api_http_requests_total` |
| Condición | 5xx sobre el total en 5 min `> 1 %` |
| Duración mínima | 2 minutos |
| Severidad | critical |
| Componente | API |
| Impacto en el Fixture | Usuarios reciben errores visibles |
| Quién atiende | Operación de la plataforma |
| Investigación y recuperación | Panel "Fallas por base" para ver qué base los origina; con el `X-Request-Id`, buscar el detalle en `api.log`. |
| Por qué ese umbral | "Error rate > 1 %" de la Clase 13. En el Hito 12 hubo 0 errores con carga, así que cualquier valor sostenido por encima ya es un cambio. |

### `BaseConErrores`

| | |
|---|---|
| Métrica | `database_errors_total` |
| Condición | fallas por segundo por base en 5 min `> 0,01` |
| Duración mínima | 2 minutos |
| Severidad | warning |
| Componente | Base de la etiqueta `database` |
| Impacto en el Fixture | Fallas intermitentes aunque el chequeo siga dando bien |
| Quién atiende | Operación de datos |
| Investigación y recuperación | La etiqueta `tipo` separa caída de timeout. Muchos timeouts con la base arriba apuntan a saturación (Hito 11). |
| Por qué ese umbral | Es el de la Clase 13: una falla cada 100 s. Es bajo a propósito, porque con poco tráfico una proporción no diría nada. |

## Capacidad

### `RedisMemoriaAlta`

| | |
|---|---|
| Métrica | `redis_memory_used_bytes`, `redis_memory_max_bytes` |
| Condición | usada sobre máxima `> 0,85` |
| Duración mínima | 2 minutos |
| Severidad | warning |
| Componente | Redis |
| Impacto en el Fixture | Al llegar a `maxmemory`, `volatile-lru` empieza a expulsar claves. Todas tienen TTL, así que puede perder sesiones y votos, y los votos no se pueden reconstruir (Hito 7). |
| Quién atiende | Operación de datos |
| Investigación y recuperación | `redis_evicted_keys_total`, `redis_db_keys`. Corto plazo: subir `maxmemory`. De fondo: separar sesiones y votos de la caché (corrección pendiente del Hito 7). |
| Por qué ese umbral | "Redis Memory at 85 %" de la Clase 14. Deja margen para reaccionar antes de expulsar. Sin probar: el laboratorio usa muy poca memoria. |

## Qué decisión habilita cada señal

| Si vemos | Hacemos |
|---|---|
| Una base caída y el resto bien | Seguimos en servicio degradado, recuperamos esa base; no se saca la API de servicio (Hito 11). |
| Sube el p95 en una ruta | Vamos a su base; no se escala todo. |
| Sube el p95 en todas las rutas | Primero la API y el host, antes que cualquier base. |
| Timeouts con la base "arriba" | Saturación: bajar carga o revisar la consulta. |
