# -*- coding: utf-8 -*-
"""Caso de uso: partidos y eventos via Neo4j (RF4), y entidad compleja /
transicion de estado via IRIS (RF8)."""

import re

from app.adapters import iris_adapter, neo4j_adapter
from app.errors import ErrorDeValidacion, RecursoNoEncontrado

_PATRON_CODIGO = re.compile(r"^[A-Za-z0-9-]{1,15}$")
ESTADOS_VALIDOS = {"Pendiente", "EnJuego", "Finalizado"}
LIMITE_EVENTOS_MAXIMO = 200


def _validar_codigo(codigo: str) -> str:
    if not _PATRON_CODIGO.match(codigo or ""):
        raise ErrorDeValidacion(f"codigo de partido invalido: {codigo!r}.")
    return codigo


def obtener_partido(codigo: str) -> dict:
    _validar_codigo(codigo)
    partido = neo4j_adapter.obtener_partido(codigo)
    if partido is None:
        raise RecursoNoEncontrado(f"No existe un partido con codigo {codigo!r}.")
    return partido


def listar_eventos(codigo: str, limite: int) -> list[dict]:
    _validar_codigo(codigo)
    if not (1 <= limite <= LIMITE_EVENTOS_MAXIMO):
        raise ErrorDeValidacion(f"limite debe estar entre 1 y {LIMITE_EVENTOS_MAXIMO}.")
    if not neo4j_adapter.existe_partido(codigo):
        raise RecursoNoEncontrado(f"No existe un partido con codigo {codigo!r}.")
    return neo4j_adapter.listar_eventos_de_partido(codigo, limite)


def obtener_entidad_compleja(codigo: str) -> dict:
    _validar_codigo(codigo)
    detalle = iris_adapter.obtener_partido_detalle(codigo)
    if detalle is None:
        raise RecursoNoEncontrado(f"IRIS no tiene registrado un partido con codigo {codigo!r}.")
    return detalle


def cambiar_estado(codigo: str, nuevo_estado: str) -> dict:
    _validar_codigo(codigo)
    if nuevo_estado not in ESTADOS_VALIDOS:
        raise ErrorDeValidacion(f"nuevo_estado invalido: {nuevo_estado!r}. Validos: {sorted(ESTADOS_VALIDOS)}.")
    resultado = iris_adapter.cambiar_estado_partido(codigo, nuevo_estado)
    if not resultado.get("existe"):
        raise RecursoNoEncontrado(f"IRIS no tiene registrado un partido con codigo {codigo!r}.")
    resultado["codigo"] = codigo
    return resultado
