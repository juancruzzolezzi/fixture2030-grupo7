# -*- coding: utf-8 -*-
"""Rutas de Equipos y Jugadores (MongoDB). Capa HTTP pura: no conoce pymongo."""

from fastapi import APIRouter, Query

from app.schemas.common import RespuestaError
from app.schemas.equipos import Equipo, JugadorDetalle, ListaEquipos, ListaJugadores
from app.services import equipos_service

equipos_router = APIRouter(prefix="/equipos", tags=["Equipos y jugadores (MongoDB)"])
jugadores_router = APIRouter(prefix="/jugadores", tags=["Equipos y jugadores (MongoDB)"])


@equipos_router.get(
    "",
    response_model=ListaEquipos,
    summary="Listar equipos, con filtro por confederacion y paginado",
    responses={400: {"model": RespuestaError}},
)
def listar_equipos(
    confederacion: str | None = Query(None, description="CONMEBOL, UEFA, CAF, AFC, CONCACAF u OFC"),
    pagina: int = Query(1, ge=1),
    tamanio_pagina: int = Query(20, ge=1, le=100),
):
    items, total = equipos_service.listar_equipos(confederacion, pagina, tamanio_pagina)
    return ListaEquipos(items=items, pagina=pagina, tamanio_pagina=tamanio_pagina, total=total)


@equipos_router.get(
    "/{codigo}",
    response_model=Equipo,
    summary="Recuperar un equipo por su codigo FIFA de 3 letras",
    responses={404: {"model": RespuestaError}},
)
def obtener_equipo(codigo: str):
    return equipos_service.obtener_equipo(codigo)


@equipos_router.get(
    "/{codigo}/jugadores",
    response_model=ListaJugadores,
    summary="Listar el plantel de un equipo, con filtro por posicion y paginado",
    responses={404: {"model": RespuestaError}, 400: {"model": RespuestaError}},
)
def listar_jugadores_de_equipo(
    codigo: str,
    posicion: str | None = Query(None, description="Arquero, Defensor, Mediocampista o Delantero"),
    pagina: int = Query(1, ge=1),
    tamanio_pagina: int = Query(20, ge=1, le=100),
):
    items, total = equipos_service.listar_jugadores_de_equipo(codigo, posicion, pagina, tamanio_pagina)
    return ListaJugadores(items=items, pagina=pagina, tamanio_pagina=tamanio_pagina, total=total)


@jugadores_router.get(
    "/{codigo}",
    response_model=JugadorDetalle,
    summary="Recuperar un jugador por su codigo (equipo+dorsal)",
    responses={404: {"model": RespuestaError}},
)
def obtener_jugador(codigo: str):
    return equipos_service.obtener_jugador(codigo)
