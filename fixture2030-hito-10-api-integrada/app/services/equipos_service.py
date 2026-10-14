# -*- coding: utf-8 -*-
"""Caso de uso: consultar equipos y jugadores (RF3). Traduce ausencia de
MongoDB a RecursoNoEncontrado; nunca deja pasar un documento interno sin
filtrar (restriccion de la consigna sobre "entregar documentos internos
completos")."""

from app.adapters import mongo_adapter
from app.errors import ErrorDeValidacion, RecursoNoEncontrado

CONFEDERACIONES_VALIDAS = {"CONMEBOL", "UEFA", "CAF", "AFC", "CONCACAF", "OFC"}
POSICIONES_VALIDAS = {"Arquero", "Defensor", "Mediocampista", "Delantero"}
TAMANIO_PAGINA_MAXIMO = 100


def _validar_paginado(pagina: int, tamanio_pagina: int):
    if pagina < 1:
        raise ErrorDeValidacion("pagina debe ser >= 1.")
    if not (1 <= tamanio_pagina <= TAMANIO_PAGINA_MAXIMO):
        raise ErrorDeValidacion(f"tamanio_pagina debe estar entre 1 y {TAMANIO_PAGINA_MAXIMO}.")


def obtener_equipo(codigo: str) -> dict:
    if not codigo or len(codigo) > 10:
        raise ErrorDeValidacion("codigo de equipo invalido.")
    equipo = mongo_adapter.obtener_equipo(codigo.upper())
    if equipo is None:
        raise RecursoNoEncontrado(f"No existe un equipo con codigo {codigo!r}.")
    return equipo


def listar_equipos(confederacion: str | None, pagina: int, tamanio_pagina: int) -> tuple[list[dict], int]:
    _validar_paginado(pagina, tamanio_pagina)
    if confederacion and confederacion.upper() not in CONFEDERACIONES_VALIDAS:
        raise ErrorDeValidacion(f"confederacion invalida: {confederacion!r}.")
    return mongo_adapter.listar_equipos(confederacion.upper() if confederacion else None, pagina, tamanio_pagina)


def obtener_jugador(codigo: str) -> dict:
    if not codigo:
        raise ErrorDeValidacion("codigo de jugador invalido.")
    jugador = mongo_adapter.obtener_jugador(codigo.upper())
    if jugador is None:
        raise RecursoNoEncontrado(f"No existe un jugador con codigo {codigo!r}.")
    return jugador


def listar_jugadores_de_equipo(equipo_id: str, posicion: str | None, pagina: int, tamanio_pagina: int) -> tuple[list[dict], int]:
    _validar_paginado(pagina, tamanio_pagina)
    if posicion and posicion not in POSICIONES_VALIDAS:
        raise ErrorDeValidacion(f"posicion invalida: {posicion!r}. Validas: {sorted(POSICIONES_VALIDAS)}.")
    # Se valida que el equipo exista antes de listar, para distinguir
    # "equipo inexistente" (404) de "equipo sin jugadores con ese filtro" (lista vacia).
    if mongo_adapter.obtener_equipo(equipo_id.upper()) is None:
        raise RecursoNoEncontrado(f"No existe un equipo con codigo {equipo_id!r}.")
    return mongo_adapter.listar_jugadores_de_equipo(equipo_id.upper(), posicion, pagina, tamanio_pagina)
