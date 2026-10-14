# -*- coding: utf-8 -*-
"""Schemas del recurso Partidos/Eventos (Neo4j, Hito 5) y de la entidad
compleja equivalente en IRIS (Hito 9)."""

from pydantic import BaseModel


class Partido(BaseModel):
    codigo: str
    fecha: str | None  # el adaptador ya convierte neo4j.time.Date a "AAAA-MM-DD"
    fase: str | None = None
    equipo_a: str
    equipo_a_nombre: str
    equipo_b: str
    equipo_b_nombre: str
    sede: str | None = None
    sede_ciudad: str | None = None


class Evento(BaseModel):
    codigo: str
    tipo: str
    minuto: int
    jugador_codigo: str
    jugador_nombre: str
    jugador_apellido: str


class ListaEventos(BaseModel):
    partido_codigo: str
    items: list[Evento]


class EventoDetalle(BaseModel):
    tipo: str
    minuto: int
    jugador: str


class PartidoDetalleIris(BaseModel):
    codigo: str
    sede: str
    local: str
    visitante: str
    estado: str
    arbitro: str
    eventos: list[EventoDetalle]


class CambioEstadoRequest(BaseModel):
    nuevo_estado: str


class CambioEstadoResponse(BaseModel):
    codigo: str
    estado_anterior: str
    estado_actual: str
    sin_cambios: bool
