# -*- coding: utf-8 -*-
"""
Hito 10 - API REST integrada del Fixture 2030 (Grupo 7).

Une, detras de contratos HTTP documentados, los seis modulos de los hitos
anteriores. No reemplaza ninguno: cada ruta termina en el adaptador de su
fuente (app/adapters/), que es el unico lugar que conoce el driver nativo
correspondiente (RNF5).
"""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.adapters import cassandra_adapter, influx_adapter, iris_adapter, mongo_adapter, neo4j_adapter, redis_adapter
from app.errors import ErrorDeAplicacion
from app.routes.comentarios_routes import router as comentarios_router
from app.routes.equipos_routes import equipos_router, jugadores_router
from app.routes.estadisticas_routes import router as estadisticas_router
from app.routes.partidos_routes import iris_router as iris_entidad_router
from app.routes.partidos_routes import router as partidos_router
from app.routes.sesiones_routes import router as sesiones_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("fixture2030.api")

app = FastAPI(
    title="Fixture 2030 - API REST Integrada",
    version="1.0.0",
    description=(
        "Capa de integracion sobre los seis modulos NoSQL del Fixture 2030 "
        "(MongoDB, Neo4j, Cassandra, Redis, InfluxDB, IRIS). Cada endpoint "
        "resuelve un caso de uso concreto; ver docs/casos_de_uso.md."
    ),
)


@app.middleware("http")
async def middleware_request_id(request: Request, call_next):
    """RF18: cada request tiene un identificador propio. Va en la respuesta
    (header) y en todas las lineas de log que produce esa request (RNF10)."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    inicio = time.monotonic()
    respuesta = await call_next(request)
    duracion_ms = (time.monotonic() - inicio) * 1000
    respuesta.headers["X-Request-Id"] = request_id
    logger.info(
        "request_id=%s metodo=%s ruta=%s status=%s duracion_ms=%.1f",
        request_id, request.method, request.url.path, respuesta.status_code, duracion_ms,
    )
    return respuesta


@app.exception_handler(ErrorDeAplicacion)
async def manejar_error_de_aplicacion(request: Request, exc: ErrorDeAplicacion):
    request_id = getattr(request.state, "request_id", "desconocido")
    if exc.detalle_interno:
        logger.warning("request_id=%s tipo=%s detalle=%s", request_id, exc.tipo, exc.detalle_interno)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"tipo": exc.tipo, "mensaje": exc.mensaje, "request_id": request_id}},
    )


@app.exception_handler(Exception)
async def manejar_excepcion_no_prevista(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "desconocido")
    logger.exception("request_id=%s error_no_previsto=%r", request_id, exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"tipo": "error_interno", "mensaje": "Error interno inesperado.", "request_id": request_id}},
    )


app.include_router(equipos_router)
app.include_router(jugadores_router)
app.include_router(partidos_router)
app.include_router(iris_entidad_router)
app.include_router(comentarios_router)
app.include_router(sesiones_router)
app.include_router(estadisticas_router)


@app.get("/salud", tags=["Operacion"], summary="Conectividad real de cada fuente (RF17, RNF11)")
def salud():
    """No cachea ni asume nada: prueba la conexion de verdad en cada llamada.
    Pensado para `scripts/verificar_conectividad.*`, no para alta frecuencia."""
    return {
        "mongodb": mongo_adapter.verificar_conectividad(),
        "neo4j": neo4j_adapter.verificar_conectividad(),
        "cassandra": cassandra_adapter.verificar_conectividad(),
        "redis": redis_adapter.verificar_conectividad(),
        "influxdb": influx_adapter.verificar_conectividad(),
        "iris": iris_adapter.verificar_conectividad(),
    }
