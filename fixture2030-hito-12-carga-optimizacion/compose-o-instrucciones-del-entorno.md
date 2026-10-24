# Entorno

Este hito no tiene un compose propio: usa las seis bases del
`docker-compose.yml` del Hito 10 (`fixture2030-hito-10-api-integrada/`), con
sus volúmenes nombrados. El flujo de la prueba usa dos de ellas, Cassandra e
InfluxDB. Las otras pueden quedar levantadas.

```
notebook
 ├─ generador de carga (scripts/ejecutar_carga.py, 30 threads)
 │     │ HTTP
 │     ▼
 ├─ API de prueba: uvicorn, 1 proceso, 127.0.0.1:8010
 │   (la levanta el script, con CASSANDRA_KEYSPACE=fixture2030_h12 e INFLUX_DATABASE=fixture2030_h12)
 │     │                         │
 │     ▼ CQL :9042               ▼ HTTP :8181
 └─ Docker: h10-cassandra     h10-influxdb      (+ mongodb, neo4j, redis, iris del Hito 10)
```

## Requisitos

- Docker Desktop (o Docker Engine) con las bases del Hito 10 levantadas y
  sembradas: `cp .env.example .env`, completar las passwords,
  `docker compose up -d` y `bash scripts/sembrar_datos.sh` (README del Hito 10).
- El venv del Hito 10 (`.venv`) con `pip install -r requirements.txt`. La
  prueba usa ese mismo Python. Lo único que agrega es `psutil`, para medir CPU
  y memoria, y `ejecutar_linea_base.sh` lo instala si falta.
- Git Bash en Windows, o cualquier bash en Linux/Mac.
- El puerto 8010 libre. La API del puerto 8000 puede estar corriendo o no: la
  prueba no la usa.

## Límites de la notebook (RNF9)

- 30 usuarios virtuales y 60 ops/s: en nuestra notebook la línea base ya se
  satura (API al 556 % de CPU) y la optimizada lo atiende con la API al 23 %.
  Para probar más, cambiar `USUARIOS_VIRTUALES` en `config/local.env` de a
  poco, nunca de golpe.
- Cada request tiene un timeout de 10 s.
- La prueba se corta sola si falla más del 20 % de las operaciones en 5 s. Con
  Ctrl+C se corta a mano y guarda lo medido hasta ahí.
- Cassandra es lo que más memoria usa: en Docker Desktop conviene tener al
  menos 6 GB asignados a la VM.

## Datos del entorno en cada resultado

Cada `resultados_*.txt` guarda sistema operativo, cantidad de CPU, RAM, versión
de Python y de las librerías, imagen y versión de Cassandra e InfluxDB, y el
commit. Por eso no los repetimos acá: dependen de la máquina donde se corre.
