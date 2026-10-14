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
Copiar `.env.example` a `.env` antes de `scripts/iniciar_api.sh`. Ningun
valor del `.env.example` es un secreto real: son las mismas credenciales de
laboratorio que ya documentaron los Hitos 4 a 9 (usuario/contraseña fijos,
sin TLS, pensados para una notebook, no para produccion).

La unica excepcion es `INFLUX_TOKEN`: InfluxDB 3 Core genera ese token en el
primer arranque (`scripts/influxdb/sembrar.sh` lo crea y lo guarda en
`.influxdb3-token`, excluido por `.gitignore`). Hay que pegar ese valor en
`.env` despues de sembrar los datos.

## Timeouts (RNF8)

Cada adaptador define su propio timeout de conexion (`app/config.py`,
`*_TIMEOUT_S`/`*_TIMEOUT_MS`), entre 2 y 3 segundos. Una base que no responde
en ese tiempo se traduce a `503 dependencia_no_disponible`, nunca a una
espera indefinida del lado del cliente HTTP.

## Orden de arranque

```bash
docker compose up -d
docker compose ps                 # esperar "healthy" en mongodb/neo4j/cassandra/redis
bash scripts/sembrar_datos.sh      # carga de prueba en las 6 fuentes
cp .env.example .env
#  -> pegar el INFLUX_TOKEN que imprimio sembrar_datos.sh
python3 -m venv .venv && source .venv/bin/activate
pip install --only-binary=:all: -r requirements.txt
bash scripts/iniciar_api.sh
```

**Nota sobre IRIS y el primer login.** La imagen Community exige cambiar la
contraseña de `_SYSTEM` la primera vez que algo se conecta por el puerto
1972 (el que usa el Native SDK de Python). `scripts/sembrar_datos.sh` ya
corre `scripts/iris/preparar_login.txt`
(`Do ##class(Security.Users).UnExpireUserPasswords("*")`) para evitarlo; si
se saltea ese paso, el adaptador de IRIS falla con
`RuntimeError('<COMMUNICATION LINK ERROR>... Password change required')`,
traducido por la API a `503 dependencia_no_disponible`.

En otra terminal:

```bash
bash scripts/verificar_conectividad.sh     # GET /salud
```

## Nota de coherencia entre fuentes (identificadores)

Mongo, Neo4j, Cassandra e InfluxDB usan los codigos `F2030-xxx` definidos
desde el Hito 4/5. **IRIS es la excepcion**: sus datos de prueba reutilizan
el codigo `M00x` que ya trae `Fixture.Demo` del Hito 9 (el propio README de
ese hito usa ese formato). Este hito no fuerza una unificacion de
identificadores entre las seis fuentes — la consigna no lo pide ("no se
exige integrar por codigo... se exige consistencia semantica"), y cambiar
los datos de IRIS para que calcen con `F2030-xxx` hubiera significado tocar
las clases del Hito 9, cosa que este modulo evita a proposito (ver
`arquitectura_y_adaptadores.md`). Se documenta la diferencia en vez de
esconderla: al probar `/partidos/{codigo}/entidad-compleja` o
`/partidos/{codigo}/estado`, el codigo a usar es `M001` o `M003` (los que
deja poblados `Fixture.Demo.Ejecutar()`), no `F2030-006`.
