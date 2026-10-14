# -*- coding: utf-8 -*-
"""Schemas del recurso Equipos/Jugadores (MongoDB, Hito 4)."""

from pydantic import BaseModel, Field


class Equipo(BaseModel):
    codigo: str = Field(..., alias="_id")
    nombre: str
    confederacion: str
    sede_mundial: bool
    ranking_fifa: int
    cantidad_jugadores: int | None = None

    model_config = {"populate_by_name": True}


class ListaEquipos(BaseModel):
    items: list[Equipo]
    pagina: int
    tamanio_pagina: int
    total: int


class JugadorResumen(BaseModel):
    codigo: str = Field(..., alias="_id")
    nombre: str
    apellido: str
    dorsal: int
    posicion: str

    model_config = {"populate_by_name": True}


class ListaJugadores(BaseModel):
    items: list[JugadorResumen]
    pagina: int
    tamanio_pagina: int
    total: int


class JugadorDetalle(BaseModel):
    codigo: str = Field(..., alias="_id")
    equipo_id: str
    nombre: str
    apellido: str
    dorsal: int
    posicion: str
    altura_cm: int | None = None
    pie_habil: str | None = None
    estadisticas: dict | None = None

    model_config = {"populate_by_name": True}
