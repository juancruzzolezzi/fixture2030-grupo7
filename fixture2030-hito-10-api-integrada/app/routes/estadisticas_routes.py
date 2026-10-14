# -*- coding: utf-8 -*-
"""Rutas de Estadisticas temporales (InfluxDB, RF7)."""

from fastapi import APIRouter, Query

from app.schemas.common import RespuestaError
from app.schemas.estadisticas import AgregacionEstadistica, VentanaEstadisticas
from app.services import estadisticas_service

router = APIRouter(prefix="/partidos/{codigo}/estadisticas", tags=["Estadisticas temporales (InfluxDB)"])


@router.get(
    "",
    response_model=VentanaEstadisticas,
    summary="Estadisticas de un equipo en una ventana de tiempo (sin agregar)",
    responses={400: {"model": RespuestaError}},
)
def ventana(
    codigo: str,
    equipo_id: str = Query(..., description="Codigo de 3 letras, p.ej. ARG"),
    desde: str = Query(..., description="ISO 8601, p.ej. 2030-06-13T14:00:00Z"),
    hasta: str = Query(..., description="ISO 8601, exclusivo"),
    limite: int = Query(50, ge=1, le=500),
):
    items = estadisticas_service.ventana(codigo, equipo_id, desde, hasta, limite)
    return VentanaEstadisticas(partido_id=codigo, equipo_id=equipo_id, desde=desde, hasta=hasta, items=items)


@router.get(
    "/agregacion",
    response_model=AgregacionEstadistica,
    summary="Agregacion correcta para el campo pedido (AVG para muestras, MAX para contadores)",
    responses={400: {"model": RespuestaError}},
)
def agregacion(
    codigo: str,
    equipo_id: str = Query(...),
    desde: str = Query(...),
    hasta: str = Query(...),
    campo: str = Query(..., description="posesion_pct, pases_completados o tiros"),
    funcion: str = Query(..., description="avg o max, segun corresponda al campo"),
):
    fila = estadisticas_service.agregacion(codigo, equipo_id, desde, hasta, campo, funcion)
    valor = fila.get("valor") if fila else None
    return AgregacionEstadistica(
        partido_id=codigo, equipo_id=equipo_id, campo=campo, funcion=funcion, desde=desde, hasta=hasta, valor=valor
    )
