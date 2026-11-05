# Validación previa (no es la evidencia final)

Corrida del 05/11/2026 para comprobar que la instrumentación, la configuración y los scripts funcionan.
**No hay que presentarla como evidencia de la plataforma**: la final se genera con la corrida completa, en
`evidencia/`, con las seis bases en Docker.

| Qué corrió de verdad | Qué no |
|---|---|
| `prometheus.yml` y `reglas-o-alertas.yml` sin cambios, en Prometheus 3.16 | Grafana: el dashboard **no se abrió**. Sus consultas sí se ejecutaron contra Prometheus. |
| redis_exporter 1.97, mongodb_exporter 0.54 (y 0.53, la imagen del compose, solo sus métricas) y node_exporter 1.12, con los parámetros del compose | Docker: el `docker-compose.yml` solo se validó con `docker compose config` |
| Redis 7 y MongoDB 8 reales (con autenticación); la API instrumentada | Neo4j, Cassandra, InfluxDB e IRIS: no había forma de instalarlos, sus rutas dan 503 reales |

`docker compose stop/start redis` se reemplazó por apagar y arrancar `redis-server`. Por eso los números de
los archivos no representan a la plataforma: el 70 % de las operaciones falla porque esas cuatro bases no existen
acá, y la máquina es otra.

**Qué queda comprobado**: 5 de 5 targets UP; `database_up` distingue las bases; al detener Redis, Prometheus lo
vio en 9 s, la alerta pasó a firing a los 69 s, la ruta dio 503, `/equipos/ARG` siguió en 200 y todo volvió solo;
las 19 consultas del dashboard se ejecutan sin error; no aparecieron secretos en la evidencia ni en `/metrics`;
y el proceso de la API no acumuló hilos ni memoria con cuatro bases caídas.
