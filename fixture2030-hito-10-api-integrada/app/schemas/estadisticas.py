# -*- coding: utf-8 -*-
"""Schemas del recurso Estadisticas (InfluxDB, Hito 8)."""

from pydantic import BaseModel


class PuntoEstadistica(BaseModel):
    time: str
    equipo_id: str
    posesion_pct: float | None = None
    pases_completados: int | None = None
    tiros: int | None = None


class VentanaEstadisticas(BaseModel):
    partido_id: str
    equipo_id: str
    desde: str
    hasta: str
    items: list[PuntoEstadistica]


class AgregacionEstadistica(BaseModel):
    partido_id: str
    equipo_id: str
    campo: str
    funcion: str
    desde: str
    hasta: str
    valor: float | None
