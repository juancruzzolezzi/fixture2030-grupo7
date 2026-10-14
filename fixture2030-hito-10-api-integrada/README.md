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
mkdir -p ~/docker/data/hito10/{cassandra,redis,influxdb,iris}
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
quedó demostrado ahí). Al final imprime el token de InfluxDB — hay que
pegarlo en `.env` (paso siguiente).

## 3. Configurar y levantar la API

```bash
cp .env.example .env
# completar INFLUX_TOKEN con el valor que imprimió sembrar_datos.sh

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
- Los identificadores de partido no están unificados entre fuentes: IRIS
  reutiliza los códigos `M00x` del Hito 9, el resto usa `F2030-xxx`. Está
  documentado en `docs/conectividad_y_configuracion.md`, no escondido.
- No se midió un volumen de producción para la API en sí: el rendimiento
  de cada fuente ya se midió en su propio hito (Cassandra en el Hito 6,
  InfluxDB en el Hito 8). Este hito mide latencia de la capa HTTP, no
  throughput de escritura masiva.
- La API no tiene autenticación propia: ningún endpoint la requiere, igual
  que ninguna de las seis bases la tiene configurada en su ambiente local.
