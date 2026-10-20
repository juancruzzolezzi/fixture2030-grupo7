# Mapa de dependencias

Quien abre todas las conexiones es el proceso de la API (uvicorn), que corre en
la notebook. Cada adaptador se conecta la primera vez que se lo necesita y
después reutiliza la conexión. Los valores salen del `.env` del Hito 10.

| Producto | Módulo | Host:puerto (desde la notebook) | Protocolo | Contexto | Autenticación | Cliente | Operación mínima | Endpoints |
|---|---|---|---|---|---|---|---|---|
| MongoDB 7 | Equipos y jugadores (H4) | localhost:27017 | MongoDB wire (TCP) | base `fixture2030` | usuario y password en `MONGO_URI` | pymongo | `equipos.find_one({_id:'ARG'})` | `/equipos`, `/jugadores` |
| Neo4j | Partidos y eventos (H5) | localhost:7687 | Bolt | base `neo4j` | `NEO4J_USER` / `NEO4J_PASSWORD` | neo4j (driver Python) | `MATCH (p:Partido {codigo:$c})` | `/partidos/{codigo}`, `/eventos` |
| Cassandra | Comentarios (H6) | localhost:9042 | CQL | keyspace `fixture2030` | no tiene | cassandra-driver | `SELECT ... WHERE partido_id=? AND bloque_horario=? LIMIT` | `/partidos/{codigo}/comentarios` |
| Redis | Sesiones y caché (H7) | localhost:6379 | RESP | db 0 | no tiene | redis-py | `HGETALL` / `TTL` de la sesión | `/sesiones`, `/partidos/{codigo}/cache` |
| InfluxDB 3 | Estadísticas (H8) | localhost:8181 | HTTP | base `fixture2030_series` | token en `INFLUX_TOKEN` | httpx | `SELECT` con ventana de tiempo y `LIMIT` | `/partidos/{codigo}/estadisticas` |
| IRIS | Entidades complejas (H9) | localhost:1972 | Superserver | namespace `USER` | `IRIS_USER` / `IRIS_PASSWORD` | Native SDK | `Fixture.ApiSupport.ObtenerPartidoDetalle` | `/entidad-compleja`, `/estado` |

Además hay dos puertos HTTP que la API no usa, pero que probamos porque es
fácil confundirlos con los "de verdad":

- Neo4j Browser en `localhost:7474`. Que abra no significa que Bolt (7687) funcione.
- Portal de IRIS en `localhost:52773`. La API entra por el Superserver (1972).

El código de partido es el mismo en todas las bases (`F2030-006`, `F2030-001`).
En el Hito 10, IRIS usaba `M001`; lo cambiamos por la devolución.

Estado esperado: todas disponibles. Estado observado: ver `evidencia/matriz.md`.
