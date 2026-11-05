# -*- coding: utf-8 -*-
"""
Metricas de la API para Prometheus (Hito 13). Prometheus las lee de GET /metrics.

Solo observa: no escribe en ninguna base ni cambia lo que responde cada ruta.
Los nombres siguen los de las Clases 13 y 14 (api_http_requests_total,
database_query_duration_seconds_bucket, database_errors_total...).

| Metrica                              | Tipo      | Que mide                                   |
|--------------------------------------|-----------|--------------------------------------------|
| api_http_requests_total              | Counter   | requests por ruta y status                 |
| api_latency_seconds                  | Histogram | duracion de la request vista por la API    |
| database_operations_total            | Counter   | llamadas a cada adaptador                  |
| database_errors_total                | Counter   | fallas de infraestructura de cada base     |
| database_query_duration_seconds      | Histogram | duracion de la llamada al adaptador        |
| database_up                          | Gauge     | 1 si el chequeo de /salud dio bien, 0 si no|
| database_check_seconds               | Gauge     | cuanto tardo ese chequeo                   |
| comentarios_creados_total            | Counter   | comentarios aceptados, por partido         |

La duracion de un adaptador incluye el driver y el cliente, no solo la base:
es lo que permitio ver en el Hito 12 que el costo estaba en crear el cliente HTTP.
"""

import re
import time
from functools import wraps

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, disable_created_metrics, generate_latest

from app.errors import ErrorDeAplicacion

CONTENT_TYPE = CONTENT_TYPE_LATEST

disable_created_metrics()  # sin las series *_created, que no usamos

# De 5 ms a 10 s: el Hito 12 midio desde ~4 ms hasta ~3,3 s. El umbral de las
# alertas (0,1 s) coincide con un limite de bucket, asi se lee sin interpolar de mas.
BUCKETS_S = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)

# Las de operacion no son trafico del Fixture: Prometheus llama a /metrics cada 15 s.
_RUTAS_OPERATIVAS = ("/metrics", "/salud", "/docs", "/redoc", "/openapi.json")

# Un codigo arbitrario no puede crear series nuevas (la cantidad de partidos es acotada: 127).
_PATRON_PARTIDO = re.compile(r"^F2030-\d{3}$")

API_REQUESTS = Counter(
    "api_http_requests", "Requests atendidas por la API", ["metodo", "ruta", "status", "clase"]
)
API_LATENCIA = Histogram(
    "api_latency_seconds", "Duracion de la request vista por la API", ["metodo", "ruta"], buckets=BUCKETS_S
)
DB_OPERACIONES = Counter(
    "database_operations", "Llamadas de la API al adaptador de cada base", ["database", "operacion"]
)
DB_ERRORES = Counter(
    "database_errors", "Fallas de infraestructura (503, 504, 500) en el adaptador", ["database", "operacion", "tipo"]
)
DB_DURACION = Histogram(
    "database_query_duration_seconds", "Duracion de la llamada al adaptador (driver + base)",
    ["database", "operacion"], buckets=BUCKETS_S,
)
DB_ARRIBA = Gauge("database_up", "1 si la base respondio el ultimo chequeo, 0 si no", ["database"])
DB_CHEQUEO = Gauge("database_check_seconds", "Duracion del ultimo chequeo de la base", ["database"])
COMENTARIOS_CREADOS = Counter("comentarios_creados", "Comentarios aceptados por partido", ["partido_id"])


def registrar_request(request, status: int, duracion_s: float) -> None:
    """Se llama desde el middleware. La ruta es el template (/equipos/{codigo}), no
    la URL real: si no, cada codigo distinto crearia una serie nueva."""
    if request.url.path.startswith(_RUTAS_OPERATIVAS):
        return
    ruta_fastapi = request.scope.get("route")
    ruta = getattr(ruta_fastapi, "path", "sin_ruta")
    API_REQUESTS.labels(request.method, ruta, str(status), f"{status // 100}xx").inc()
    API_LATENCIA.labels(request.method, ruta).observe(duracion_s)


def _medir(funcion, database: str, operacion: str):
    @wraps(funcion)
    def medida(*args, **kwargs):
        DB_OPERACIONES.labels(database, operacion).inc()
        inicio = time.perf_counter()
        try:
            return funcion(*args, **kwargs)
        except ErrorDeAplicacion as exc:
            # Un 409 de IRIS o un 400 son respuestas correctas de negocio, no fallas de la base.
            if exc.status_code >= 500:
                DB_ERRORES.labels(database, operacion, exc.tipo).inc()
            raise
        except Exception:
            DB_ERRORES.labels(database, operacion, "no_prevista").inc()
            raise
        finally:
            DB_DURACION.labels(database, operacion).observe(time.perf_counter() - inicio)

    return medida


def instrumentar_adaptadores(operaciones: dict) -> None:
    """Envuelve las operaciones de cada adaptador sin tocar su codigo. Los servicios
    las llaman como modulo.funcion(...), asi que usan la version medida."""
    for (modulo, database), nombres in operaciones.items():
        for nombre in nombres:
            setattr(modulo, nombre, _medir(getattr(modulo, nombre), database, nombre))


def actualizar_salud(dependencias: dict) -> None:
    """Pasa el resultado del chequeo de /salud a los gauges."""
    for database, resultado in dependencias.items():
        DB_ARRIBA.labels(database).set(1 if resultado["estado"] == "up" else 0)
        DB_CHEQUEO.labels(database).set(resultado["ms"] / 1000)


def contar_comentario(partido_id: str) -> None:
    COMENTARIOS_CREADOS.labels(partido_id if _PATRON_PARTIDO.match(partido_id) else "otro").inc()


def exportar() -> bytes:
    return generate_latest()
