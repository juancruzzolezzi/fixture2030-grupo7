# -*- coding: utf-8 -*-
"""Rutas de Partidos/Eventos (Neo4j, RF4) y de la entidad compleja /
transicion de estado (IRIS, RF8)."""

from fastapi import APIRouter, Query

from app.schemas.common import RespuestaError
from app.schemas.partidos import (
    CambioEstadoRequest,
    CambioEstadoResponse,
    ListaEventos,
    Partido,
    PartidoDetalleIris,
)
from app.services import partidos_service

router = APIRouter(prefix="/partidos", tags=["Partidos y eventos (Neo4j)"])
iris_router = APIRouter(prefix="/partidos", tags=["Entidad compleja de partido (IRIS)"])


@router.get(
    "/{codigo}",
    response_model=Partido,
    summary="Recuperar un partido con sus dos equipos y la sede (Cypher parametrizado)",
    responses={404: {"model": RespuestaError}},
)
def obtener_partido(codigo: str):
    return partidos_service.obtener_partido(codigo)


@router.get(
    "/{codigo}/eventos",
    response_model=ListaEventos,
    summary="Eventos de un partido con el jugador que los protagonizo (recorrido de 2 relaciones)",
    responses={404: {"model": RespuestaError}, 400: {"model": RespuestaError}},
)
def listar_eventos(codigo: str, limite: int = Query(30, ge=1, le=200)):
    items = partidos_service.listar_eventos(codigo, limite)
    return ListaEventos(partido_codigo=codigo, items=items)


@iris_router.get(
    "/{codigo}/entidad-compleja",
    response_model=PartidoDetalleIris,
    summary="Detalle de objeto completo del partido (arbitro + eventos), navegado dentro de IRIS",
    responses={404: {"model": RespuestaError}},
)
def obtener_entidad_compleja(codigo: str):
    return partidos_service.obtener_entidad_compleja(codigo)


@iris_router.patch(
    "/{codigo}/estado",
    response_model=CambioEstadoResponse,
    summary="Avanzar el estado del partido (maquina de estados validada dentro de IRIS)",
    responses={404: {"model": RespuestaError}, 400: {"model": RespuestaError}, 409: {"model": RespuestaError}},
)
def cambiar_estado(codigo: str, cuerpo: CambioEstadoRequest):
    resultado = partidos_service.cambiar_estado(codigo, cuerpo.nuevo_estado)
    return CambioEstadoResponse(**resultado)
