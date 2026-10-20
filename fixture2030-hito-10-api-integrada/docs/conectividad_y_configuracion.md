# Conectividad y configuracion

## Dos ambientes distintos: notebook vs. contenedor

Las seis bases corren en Docker (`docker-compose.yml`, en esta misma
carpeta); **la API corre en la notebook**, fuera de Docker, con
`uvicorn app.main:app`. Por eso todos los hosts de `.env.example` son
`localhost`: la API se conecta a los puertos publicados por cada contenedor,
no a un nombre de servicio de Compose. Si en algun momento la API tambien se
dockerizara, esos hosts pasarian a ser los nombres de servicio
(`mongodb`, `neo4j`, etc.) en vez de `localhost` — es la distincion que pide
RNF11/RF13 sobre "la prueba desde la notebook y la prueba desde un
contenedor pueden requerir hosts y puertos diferentes".

## Variables de entorno (RNF6, RNF7)

Todo host/puerto/credencial sale de variables de entorno (`app/config.py`).
Hay que copiar `.env.example` a `.env` antes de `docker compose up`, y poner
passwords propias en lugar de los valores `CAMBIAR_...`. El `.env` no se
versiona. Lo leen Docker Compose (para crear los usuarios de MongoDB y
Neo4j), `scripts/sembrar_datos.sh` (que le pone esa password a IRIS) y la API.
El código no tiene passwords por defecto.

`INFLUX_TOKEN` lo genera InfluxDB 3 Core la primera vez. `scripts/influxdb/sembrar.sh`
lo guarda en `.influxdb3-token` (excluido por `.gitignore`) y
`scripts/sembrar_datos.sh` lo copia al `.env`.

## Timeouts (RNF8)

Cada adaptador define su propio timeout de conexion (`app/config.py`,
`*_TIMEOUT_S`/`*_TIMEOUT_MS`), entre 2 y 3 segundos. Una base que no responde
en ese tiempo se traduce a `503 dependencia_no_disponible`, nunca a una
espera indefinida del lado del cliente HTTP.

## Orden de arranque

```bash
cp .env.example .env              # y completar las passwords CAMBIAR_...
docker compose up -d
docker compose ps                 # esperar "healthy" en mongodb/neo4j/cassandra/redis
bash scripts/sembrar_datos.sh      # carga de prueba en las 6 fuentes (copia el token de Influx al .env)
python3 -m venv .venv && source .venv/bin/activate
pip install --only-binary=:all: -r requirements.txt
bash scripts/iniciar_api.sh
```

**Nota sobre IRIS y el primer login.** La imagen Community exige cambiar la
contraseña de `_SYSTEM` la primera vez que algo se conecta por el puerto
1972 (el que usa el Native SDK de Python). `scripts/sembrar_datos.sh` corre
`scripts/iris/preparar_login.txt`, que le asigna a `_SYSTEM` la password de
`IRIS_PASSWORD` del `.env` y la marca como vigente. Si se saltea ese paso, el adaptador de IRIS falla con
`RuntimeError('<COMMUNICATION LINK ERROR>... Password change required')`,
traducido por la API a `503 dependencia_no_disponible`.

En otra terminal:

```bash
bash scripts/verificar_conectividad.sh     # GET /salud
```

## Identificador de partido común

Todas las fuentes usan el mismo código de partido, `F2030-xxx`. En la entrega
original IRIS usaba los `M00x` de `Fixture.Demo` del Hito 9, y el consumidor
tenía que saber qué base atendía cada ruta para elegir el código (devolución
del Hito 10). Ahora `scripts/iris/sembrar.txt` corre además
`Fixture.ApiSupport.SembrarPartidosF2030()`, que carga en IRIS los mismos
partidos que el resto (`F2030-006` y `F2030-001`), y `partidos_service.py`
rechaza con 400 cualquier código que no tenga ese formato.
