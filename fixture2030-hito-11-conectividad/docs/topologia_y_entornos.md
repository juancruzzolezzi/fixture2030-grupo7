# Topología y entornos

```
 notebook
 ┌───────────────────────────┐         Docker Compose (red interna del compose del Hito 10)
 │ API (uvicorn :8000)       │         ┌─────────────────────────────────────────────┐
 │  localhost:27017 ─────────┼────────►│ h10-mongodb    27017                         │
 │  localhost:7687  ─────────┼────────►│ h10-neo4j      7687 (Bolt), 7474 (HTTP)      │
 │  localhost:9042  ─────────┼────────►│ h10-cassandra  9042                          │
 │  localhost:6379  ─────────┼────────►│ h10-redis      6379                          │
 │  localhost:8181  ─────────┼────────►│ h10-influxdb   8181                          │
 │  localhost:1972  ─────────┼────────►│ h10-iris       1972 (Superserver), 52773     │
 │                           │         └─────────────────────────────────────────────┘
 │ evaluar_conectividad.py   │   (mismo origen que la API: corre en la notebook con el mismo venv)
 └───────────────────────────┘
```

- La API corre en la notebook, fuera de Docker. Por eso todos los hosts son
  `localhost` y los puertos son los que publica cada contenedor.
- En nuestro compose el puerto publicado y el interno son iguales en todos los
  casos (27017:27017, 6379:6379, etc.). InfluxDB e IRIS se publican solo en
  `127.0.0.1`. Las demás bases se publican en todas las interfaces de la notebook.
- El script de evaluación corre en el mismo lugar que la API y con el mismo
  venv, así que prueba el mismo camino que usa la API.
- La prueba con el cliente de línea de comandos (mongosh, cqlsh, redis-cli,
  cypher-shell, iris) se hace con `docker exec`, así que sale desde adentro del
  contenedor de la base. Sirve para ver si la base anda aunque la API no.

## Qué cambiaría si la API corriera en un contenedor

Adentro de un contenedor, `localhost` es el propio contenedor, no la notebook.
Si la API estuviera en la misma red del compose, habría que usar los nombres de
servicio (`mongodb`, `neo4j`, `cassandra`, `redis`, `influxdb`, `iris`) y los
puertos internos. Con el `.env` actual fallaría con "connection refused".

Al revés también pasa. Desde la notebook, un nombre de servicio no existe: el
script lo prueba con `mongodb:27017` y da "host no resuelto" (contraste en
`evidencia/resultados_tcp.txt`).
