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
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app import metricas
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

# Hito 13: Prometheus mide cada operacion de los adaptadores que usan las rutas.
metricas.instrumentar_adaptadores({
    (mongo_adapter, "mongodb"): ["obtener_equipo", "listar_equipos", "obtener_jugador", "listar_jugadores_de_equipo"],
    (neo4j_adapter, "neo4j"): ["obtener_partido", "listar_eventos_de_partido", "existe_partido"],
    (cassandra_adapter, "cassandra"): ["listar_comentarios", "crear_comentario"],
    (redis_adapter, "redis"): ["obtener_sesion", "obtener_cache_partido", "invalidar_cache_partido"],
    (influx_adapter, "influxdb"): ["estadisticas_ventana", "estadisticas_agregadas"],
    (iris_adapter, "iris"): ["obtener_partido_detalle", "cambiar_estado_partido"],
})

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
    try:
        respuesta = await call_next(request)
    except Exception:
        metricas.registrar_request(request, 500, time.monotonic() - inicio)  # Hito 13
        raise
    duracion_ms = (time.monotonic() - inicio) * 1000
    metricas.registrar_request(request, respuesta.status_code, duracion_ms / 1000)  # Hito 13
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


# --- Salud (Hito 11) ----------------------------------------------------------
# /salud/vivo   liveness: el proceso responde, no toca ninguna base.
# /salud/listo  readiness: up / degraded (200) o down (503, ninguna base responde).
# /salud        detalle por dependencia (estado y milisegundos).
# El chequeo de las bases se reutiliza 10 s para no consultarlas en cada sonda.

_VERIFICADORES = {
    "mongodb": mongo_adapter.verificar_conectividad,
    "neo4j": neo4j_adapter.verificar_conectividad,
    "cassandra": cassandra_adapter.verificar_conectividad,
    "redis": redis_adapter.verificar_conectividad,
    "influxdb": influx_adapter.verificar_conectividad,
    "iris": iris_adapter.verificar_conectividad,
}
CACHE_SALUD_S = 10
_ultimo_chequeo = {"momento": 0.0, "resultado": None}


def _chequear_dependencias(forzar: bool = False) -> dict:
    if not forzar and time.monotonic() - _ultimo_chequeo["momento"] < CACHE_SALUD_S:
        return _ultimo_chequeo["resultado"]

    def medir(funcion):
        inicio = time.monotonic()
        ok = funcion()
        return {"estado": "up" if ok else "down", "ms": round((time.monotonic() - inicio) * 1000, 1)}

    # En paralelo: una base colgada no suma su timeout al de las demas.
    with ThreadPoolExecutor(max_workers=len(_VERIFICADORES)) as pool:
        futuros = {nombre: pool.submit(medir, f) for nombre, f in _VERIFICADORES.items()}
        resultado = {nombre: futuro.result() for nombre, futuro in futuros.items()}
    _ultimo_chequeo.update(momento=time.monotonic(), resultado=resultado)
    return resultado


def _estado_general(dependencias: dict) -> str:
    arriba = sum(1 for d in dependencias.values() if d["estado"] == "up")
    if arriba == len(dependencias):
        return "up"
    return "down" if arriba == 0 else "degraded"


@app.get("/salud/vivo", tags=["Operacion"], summary="Liveness: el proceso de la API responde (no consulta bases)")
def salud_vivo():
    return {"estado": "up"}


@app.get("/salud/listo", tags=["Operacion"], summary="Readiness: up/degraded (200) o down (503)",
         responses={503: {"description": "Ninguna dependencia responde"}})
def salud_listo():
    dependencias = _chequear_dependencias()
    estado = _estado_general(dependencias)
    cuerpo = {"estado": estado, "dependencias": {k: v["estado"] for k, v in dependencias.items()}}
    return JSONResponse(status_code=503 if estado == "down" else 200, content=cuerpo)


@app.get("/salud", tags=["Operacion"], summary="Estado y latencia de cada dependencia")
def salud(forzar: bool = False):
    """Con ?forzar=true no usa el resultado guardado (para diagnostico manual)."""
    dependencias = _chequear_dependencias(forzar)
    return {"estado": _estado_general(dependencias), "dependencias": dependencias}


# --- Metricas para Prometheus (Hito 13) ---------------------------------------
# Prometheus la llama cada 15 s. Reutiliza el chequeo de /salud (hace ping o una
# lectura minima por base, nunca escribe) y lo publica como database_up.

@app.get("/metrics", tags=["Operacion"], summary="Metricas en formato Prometheus", include_in_schema=False)
def exponer_metricas():
    metricas.actualizar_salud(_chequear_dependencias())
    return Response(content=metricas.exportar(), media_type=metricas.CONTENT_TYPE)
