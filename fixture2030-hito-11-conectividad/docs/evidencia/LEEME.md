# Evidencia

Estos archivos los generan los scripts (se pisan en cada corrida):

- `resultados_tcp.txt`, `resultados_clientes.txt`, `resultados_api.txt` (+ `.json`): `scripts/evaluar_conectividad.py`
- `matriz.md`: la arma el mismo script al final
- `escenario_redis.txt`, `escenario_influxdb.txt`, `escenario_iris.txt`: `scripts/escenario_falla.sh`

Las passwords y el token de Influx salen como `***`.

Capturas (`capturas_redactadas/`), tomadas sin credenciales a la vista:

1. `docker compose ps` con las 6 bases arriba
2. el final de `evaluar_conectividad.py` con la matriz
3. `http://localhost:8000/salud?forzar=true` con Redis detenido (estado `degraded`)
