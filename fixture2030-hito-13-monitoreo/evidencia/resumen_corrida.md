# Resumen de la corrida
Fecha: 2026-11-05T22:24:20-03:00 | commit: 9b05452 | archivos sin commitear: 0
Entorno: Windows 11, 16 CPU logicas, Python 3.12.10
Imagenes: fixture2030-prometheus=prom/prometheus:latest@e04987641b57, fixture2030-grafana=grafana/grafana:latest@488984b716c0, fixture2030-node-exporter=prom/node-exporter:latest@1b4e4438faca, fixture2030-redis-exporter=oliver006/redis_exporter:latest@f5f903fbe775, fixture2030-mongodb-exporter=percona/mongodb_exporter:0.53@0214e482b2cd, h10-mongodb=mongo:7.0@b6421fd6d1c5, h10-neo4j=neo4j:latest@dbc377fb9cd8, h10-cassandra=cassandra:latest@da9dad3aaf67, h10-redis=redis:latest@718f745deb7d, h10-influxdb=influxdb:3-core@26875ba5ae6e, h10-iris=intersystems/iris-community:latest-cd@cd2ebcab02d1

| Medido | Valor | Detalle |
|---|---|---|
| Operaciones de la carga (30 usuarios, 60 ops/s pedidas) | 10179, 10179 exitosas, 0 sin respuesta | `resultados_sin_secretos/carga.txt` |
| Tasa promedio, incluida la rampa | 56.2 ops/s | Igual |
| p95 total, medido por el generador | 37.2 ms | Igual |
| Redis detenido: Prometheus ve `database_up=0` | 7.6 s | `prueba_de_falla.txt` |
| Redis detenido: alerta `BaseDeDatosCaida` en firing | 90.3 s | Igual |
| Redis vuelve: la ruta responde 200 | 0.5 s | Igual |
