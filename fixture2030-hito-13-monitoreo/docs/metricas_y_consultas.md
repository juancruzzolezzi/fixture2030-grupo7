# Métricas y consultas PromQL

## Métricas de aplicación e infraestructura

| Tipo de métrica | De dónde sale | Ejemplos | Qué pregunta responde |
|---|---|---|---|
| Aplicación | `/metrics` de la API | `api_http_requests_total`, `api_latency_seconds`, `database_*`, `comentarios_creados_total` | ¿Cómo le va al Fixture visto desde quien lo usa? |
| Infraestructura | Exporters | `redis_*`, `mongodb_*`, `node_*` | ¿Cómo están los recursos y los motores? |

Tipos de la clase que usamos: **Counter** (`api_http_requests_total`, solo sube), **Gauge**
(`database_up`, sube y baja) e **Histogram** (`api_latency_seconds_bucket`). No usamos Summary:
sus cuantiles se calculan en cada proceso y no se pueden sumar entre rutas; el histograma sí, con
`sum by (le)`.

Las etiquetas de ruta usan el template (`/equipos/{codigo}`), no la URL real: si no, cada código
crearía una serie nueva. Las rutas `/metrics` y `/salud*` no se cuentan como tráfico.

## Consultas

Todas son del dashboard, salvo que se indique otra cosa, y se pueden pegar en http://localhost:9090/graph.

### 1. Latencia p95 de la API por ruta

```promql
histogram_quantile(0.95, sum by (le, ruta) (rate(api_latency_seconds_bucket[1m])))
```

- **Mide**: el tiempo por debajo del cual está el 95 % de las requests de cada ruta.
- **Unidad**: segundos. **Período**: ventana de 1 minuto. En la alerta, 5 minutos.
- **Se lee**: es una estimación entre límites de bucket (5, 10, 25, 50, 100 ms...), no un valor
  exacto. Por eso puede diferir del p95 que calcula el generador.

### 2. Errores por segundo por base

```promql
sum by (database, tipo) (rate(database_errors_total[1m]))
```

- **Mide**: fallas de infraestructura en cada adaptador; `tipo` separa base caída
  (`dependencia_no_disponible`, 503) de timeout (`timeout_dependencia`, 504).
- **Unidad**: fallas por segundo. **Período**: ventana de 1 minuto.
- **Se lee**: un 404 o un 409 no aparecen acá porque son respuestas correctas de negocio.

### 3. Proporción de respuestas 5xx

```promql
sum(rate(api_http_requests_total{clase="5xx"}[1m])) / sum(rate(api_http_requests_total[1m]))
```

- **Mide**: qué parte de las requests terminó en falla del servidor.
- **Unidad**: proporción de 0 a 1. **Período**: ventana de 1 minuto.
- **Se lee**: sin series significa que no hubo ningún 5xx en el período, no que falte el dato.

### 4. Throughput por base

```promql
sum by (database) (rate(database_operations_total[1m]))
```

- **Mide**: operaciones por segundo que la API le pide a cada base.
- **Unidad**: operaciones por segundo. **Período**: ventana de 1 minuto.
- **Se lee**: muestra cómo se reparte el tráfico entre módulos. No dice cómo se reparten los datos
  entre nodos: en el laboratorio hay un nodo por base.

### 5. Estado de cada base

```promql
database_up
```

- **Mide**: si el último chequeo de la API llegó a esa base. **Unidad**: 1 o 0. **Período**: instantánea, cada 15 s.

### 6. ¿La API o la base?

```promql
histogram_quantile(0.95, sum by (le) (rate(api_latency_seconds_bucket[1m])))
histogram_quantile(0.95, sum by (le) (rate(database_query_duration_seconds_bucket[1m])))
```

- **Mide**: el p95 total de la API y el de los adaptadores. **Unidad**: segundos. **Período**: 1 minuto.
- **Se lee**: si sube la primera y no la segunda, el tiempo se va en la API. Si suben las dos, está
  en un adaptador. Para saber si es el driver o la base, comparar con el motor: en Redis y MongoDB
  con sus exporters; en las demás, con `docker stats`.

### 7. Memoria de Redis sobre su límite

```promql
redis_memory_used_bytes / (redis_memory_max_bytes > 0)
```

- **Mide**: qué parte de `maxmemory` está en uso. **Unidad**: proporción. **Período**: instantánea.
- **Se lee**: el `> 0` evita dividir por cero si Redis corre sin `maxmemory`.

### 8. CPU del host Docker

```promql
1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))
```

- **Mide**: parte del tiempo que la CPU no está ociosa. **Unidad**: proporción. **Período**: 1 minuto.
- **Se lee**: en Docker Desktop es la VM de los contenedores. La API corre afuera.

## Cómo se relacionan con los objetivos del TPO (RF11)

| Objetivo | Métrica que lo observa | Qué se puede afirmar | Qué no |
|---|---|---|---|
| Concurrencia | Usuarios de `generar_carga.py`, `redis_connected_clients`, `mongodb_ss_connections` | Comportamiento con los usuarios simulados | Miles de usuarios reales |
| Throughput | `api_http_requests_total`, `database_operations_total` | ops/s alcanzadas contra las pedidas | La capacidad máxima: no hicimos la prueba por escalones |
| Latencia | `api_latency_seconds`, `database_query_duration_seconds` | p95 por ruta y por base en la notebook | La latencia entre regiones |
| Disponibilidad | `up`, `database_up`, 5xx | Qué estaba caído y cuánto | Disponibilidad de un clúster: no hay réplicas |
| Distribución | `database_operations_total` por base | Reparto del tráfico entre modelos | Reparto entre nodos o regiones |
| Recuperación | `prueba_de_falla.txt`: tiempo de detección y de vuelta a 200 | Recuperación de una base que se detiene y arranca en el mismo nodo | Conmutación a una réplica |
