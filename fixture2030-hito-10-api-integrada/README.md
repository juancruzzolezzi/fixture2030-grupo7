# Hito 10 - API REST integrada del Fixture 2030 (Grupo 7)

Capa de integración HTTP sobre los seis módulos NoSQL que ya construimos:
MongoDB (Hito 4), Neo4j (Hito 5), Cassandra (Hito 6), Redis (Hito 7),
InfluxDB (Hito 8) e IRIS (Hito 9). No reemplaza ninguno: cada ruta termina
en el adaptador de su fuente, que es el único lugar que conoce el driver
nativo correspondiente.

Las decisiones de diseño están separadas por tema en `docs/`. Este README
es la parte operativa.

## Requisitos

- Docker Desktop (o Docker Engine + Compose).
- Python 3.10+.
- ~4 GB libres para las seis imágenes (IRIS es la más pesada).

## 1. Levantar las seis bases

```bash
cp .env.example .env     # y reemplazar las tres passwords CAMBIAR_... (el .env no se versiona)
docker compose up -d
docker compose ps        # esperar "healthy" en mongodb, neo4j, cassandra, redis
```

InfluxDB e IRIS no traen healthcheck en este compose (igual que en sus
hitos de origen); el paso de siembra espera a que respondan.

## 2. Sembrar datos de prueba en las seis fuentes

```bash
bash scripts/sembrar_datos.sh
```

Es una muestra chica y reproducible pensada solo para probar la
integración: no reemplaza la evidencia de volumen de cada hito (eso ya
quedó demostrado ahí). También copia el token de InfluxDB al `.env` y le
pone a IRIS la password del `.env`.

## 3. Configurar y levantar la API

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --only-binary=:all: -r requirements.txt
bash scripts/iniciar_api.sh
```

`--only-binary=:all:` evita que `cassandra-driver` intente compilar desde
el paquete fuente en Python 3.12+ (el instalador viejo que trae no es
compatible; el mismo problema que ya documentamos en el Hito 6).

La API queda en `http://localhost:8000`. Swagger UI: `http://localhost:8000/docs`.

## 4. Verificar conectividad

```bash
bash scripts/verificar_conectividad.sh
```

Pega contra `GET /salud`, que prueba la conexión real a las seis fuentes
(no un valor cacheado).

## 5. Exportar el contrato OpenAPI

```bash
python3 scripts/exportar_openapi.py
```

Vuelca `openapi/openapi.yaml` desde la propia aplicación — nunca se edita
a mano, para que no describa algo que la API no hace.

## 6. Correr las pruebas

```bash
bash scripts/ejecutar_pruebas.sh
```

`tests/integration/test_endpoints.py` cubre, por cada fuente: una
operación válida, un parámetro inválido y un recurso inexistente.
`tests/integration/test_dependencia_caida.py` para de verdad el contenedor
de Redis, confirma el `503` y lo vuelve a levantar — no es un mock.

## Postman

`postman/fixture2030_collection.json`: importar en Postman, variable
`base_url` ya apunta a `http://localhost:8000`.

## Cambios hechos en el Hito 11

Al evaluar la conectividad (ver `fixture2030-hito-11-conectividad/`) se
corrigieron estas cosas de la API:

- `GET /salud/vivo` (liveness) y `GET /salud/listo` (readiness); `GET /salud`
  ahora da estado y milisegundos por dependencia.
- Un timeout de la base devuelve **504** `timeout_dependencia`; una base caída
  sigue siendo **503**. Antes todo era 503 "no respondió a tiempo", incluso una
  password incorrecta de Neo4j.
- Redis reintenta una sola vez (antes 3, por defecto de redis-py: el 503 tardaba ~4,8 s).
- IRIS: timeout de conexión explícito y reconexión si IRIS se reinicia (antes
  quedaba en 503 hasta reiniciar la API).
- Código de partido único `F2030-xxx` también en IRIS (devolución del Hito 10).
- Volúmenes nombrados para todas las bases (devolución del Hito 6).

## Estructura

```
app/
  adapters/      un archivo por fuente (unico lugar que importa su driver)
  services/      casos de uso: validan y deciden 400/404/409/503
  routes/        rutas FastAPI, sin logica de negocio
  schemas/       modelos Pydantic de entrada/salida
  config.py      variables de entorno
  errors.py      taxonomia de errores
  main.py        arma la app, middleware de request_id, manejo de errores
docker-compose.yml       las 6 bases (no la API: esa corre en la notebook)
scripts/
  sembrar_datos.sh        carga de prueba en las 6 fuentes
  iniciar_api.sh           uvicorn con .env cargado
  verificar_conectividad.sh
  ejecutar_pruebas.sh
  exportar_openapi.py
  mongo/ neo4j/ cassandra/ redis/ influxdb/ iris/   datos y scripts de siembra por fuente
openapi/openapi.yaml     contrato, generado desde la app
postman/fixture2030_collection.json
tests/integration/       pruebas contra la API real
docs/                    casos de uso, arquitectura, contratos, conectividad, pruebas
```

## Alcance y limitaciones

- No se integran las seis fuentes en una sola request: cada caso de uso
  justifica su propia combinación (ver `docs/arquitectura_y_adaptadores.md`,
  sección "Combinación de fuentes").
- Los identificadores de partido están unificados: todas las fuentes, IRIS
  incluido, usan `F2030-xxx` (corregido después de la devolución; antes IRIS
  usaba los `M00x` del Hito 9).
- No se midió un volumen de producción para la API en sí: el rendimiento
  de cada fuente ya se midió en su propio hito (Cassandra en el Hito 6,
  InfluxDB en el Hito 8). Este hito mide latencia de la capa HTTP, no
  throughput de escritura masiva.
- La API no tiene autenticación propia: ningún endpoint la requiere, igual
  que ninguna de las seis bases la tiene configurada en su ambiente local.
- Hito 12: el adaptador de InfluxDB usa un solo cliente HTTP con pool de
  conexiones (`INFLUX_REUSAR_CLIENTE=1`). Con `0` vuelve a crear un cliente
  por consulta, como antes. La medición está en `../fixture2030-hito-12-carga-optimizacion/`.
