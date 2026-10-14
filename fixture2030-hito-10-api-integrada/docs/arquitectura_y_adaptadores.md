# Arquitectura y adaptadores

```
Cliente HTTP
    ↓
app/routes/*      — rutas FastAPI: parsea path/query/body, nada de logica de negocio
    ↓
app/services/*    — caso de uso: valida, decide 404/400/409, llama UN adaptador (o dos, ver abajo)
    ↓
app/adapters/*    — un archivo por fuente: abre la conexion, arma la consulta nativa,
                     traduce la excepcion del driver a DependenciaNoDisponible/ErrorInterno
    ↓
driver nativo (pymongo / neo4j / cassandra-driver / redis-py / httpx / iris native SDK)
    ↓
Base NoSQL
```

Nadie fuera de `app/adapters/<fuente>_adapter.py` importa el driver de esa
fuente (RNF5). Si mañana cambia el driver de Mongo, el único archivo que se
toca es `mongo_adapter.py`.

## Por que un adaptador por fuente y no una interfaz comun

Las seis fuentes no comparten forma de consulta: una es documental con
filtro+paginado, otra es un grafo con Cypher parametrizado, otra es una
tabla con clave de particion obligatoria, otra es clave-valor con TTL, otra
es SQL sobre series temporales, y la ultima es un objeto que valida su
propia maquina de estados. Forzar una interfaz comun (`get(id)`,
`query(filtro)`) escondería justamente las diferencias que la consigna pide
conservar ("una consulta documental, un recorrido de grafo, una lectura por
particion... no se ejecutan de la misma manera aunque todos se expongan
mediante HTTP y JSON"). Cada adaptador expone las funciones que su propio
caso de uso necesita, no una interfaz generica.

## Combinacion de fuentes: el recurso "partido"

`/partidos/{codigo}` vive en tres adaptadores distintos, sin que eso
implique una fuente unica:

- `GET /partidos/{codigo}` y `GET /partidos/{codigo}/eventos` → Neo4j (RF4).
- `GET /partidos/{codigo}/entidad-compleja` y `PATCH /partidos/{codigo}/estado` → IRIS (RF8).
- `GET /partidos/{codigo}/comentarios` y `POST /partidos/{codigo}/comentarios` → Cassandra (RF5).
- `GET /partidos/{codigo}/cache` y `DELETE /partidos/{codigo}/cache` → Redis (RF6).
- `GET /partidos/{codigo}/estadisticas` → InfluxDB (RF7).

Es el mismo concepto de dominio ("partido"), pero cada ruta termina en un
adaptador distinto y ninguna combina dos fuentes en la misma request (la
consigna aclara explicitamente que no hace falta). La unica excepcion es
`comentarios_service.crear_comentario`, que escribe en dos tablas de la
*misma* fuente (Cassandra): eso es la duplicacion controlada que ya
documentó el Hito 6, no una integracion entre bases.

## Manejo de errores (RF11, RF12, RNF4)

Una sola jerarquia de excepciones (`app/errors.py`) y un solo manejador en
`main.py` que las traduce a:

| Excepcion | HTTP | Cuando |
|---|---|---|
| `ErrorDeValidacion` | 400 | Parametro de ruta/query/body invalido. Nunca se llega a tocar la fuente. |
| `RecursoNoEncontrado` | 404 | La fuente respondio, el recurso no existe. |
| `ConflictoDeNegocio` | 409 | El estado actual no permite la operacion (p.ej. transicion ilegal en IRIS). |
| `DependenciaNoDisponible` | 503 | La fuente no respondio a tiempo (timeout, conexion rechazada). |
| `ErrorInterno` | 500 | Cualquier otra falla no prevista. |

Todas devuelven el mismo formato (`{"error": {"tipo", "mensaje", "request_id"}}`)
y nunca el detalle tecnico del driver: ese detalle va solo al log, bajo el
mismo `request_id` que trae la respuesta (header `X-Request-Id`), para poder
correlacionar sin exponer nada sensible (RNF10).

## Por que no hay una capa de "cache" ni "colas" propia de la API

La API no agrega su propio estado (no hay una base propia de la API). Cada
adaptador abre su conexion de forma perezosa (la primera vez que se usa) y
la reutiliza: si Redis está caído al arrancar la API, eso no tira abajo el
resto de los endpoints — recién falla, con 503, el primer request que
efectivamente necesite Redis (RNF9).
