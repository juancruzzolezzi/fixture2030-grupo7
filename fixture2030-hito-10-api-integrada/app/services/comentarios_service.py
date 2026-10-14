# -*- coding: utf-8 -*-
"""Caso de uso: comentarios de un partido via Cassandra (RF5). El
bloque_horario es un parametro de ruta obligatorio: no existe una consulta
"todos los comentarios del partido" sin ese dato, porque la tabla no esta
particionada para resolverla (ver Hito 6, decisiones_de_particionamiento.md)."""

import re

from app.adapters import cassandra_adapter
from app.errors import ErrorDeValidacion

_PATRON_PARTIDO = re.compile(r"^[A-Za-z0-9-]{1,15}$")
_PATRON_BLOQUE = re.compile(r"^\d{12}$")  # AAAAMMDDHHmm, igual que el Hito 6
LIMITE_MAXIMO = 100


def listar_comentarios(partido_id: str, bloque_horario: str, limite: int) -> list[dict]:
    if not _PATRON_PARTIDO.match(partido_id or ""):
        raise ErrorDeValidacion(f"partido_id invalido: {partido_id!r}.")
    if not _PATRON_BLOQUE.match(bloque_horario or ""):
        raise ErrorDeValidacion(f"bloque_horario invalido: {bloque_horario!r}. Formato esperado AAAAMMDDHHmm.")
    if not (1 <= limite <= LIMITE_MAXIMO):
        raise ErrorDeValidacion(f"limite debe estar entre 1 y {LIMITE_MAXIMO}.")
    return cassandra_adapter.listar_comentarios(partido_id, bloque_horario, limite)


def crear_comentario(partido_id: str, bloque_horario: str, usuario_id: str, usuario_nombre: str, contenido: str, clave_idempotencia: str) -> dict:
    if not _PATRON_PARTIDO.match(partido_id or ""):
        raise ErrorDeValidacion(f"partido_id invalido: {partido_id!r}.")
    if not _PATRON_BLOQUE.match(bloque_horario or ""):
        raise ErrorDeValidacion(f"bloque_horario invalido: {bloque_horario!r}. Formato esperado AAAAMMDDHHmm.")
    if not contenido.strip():
        raise ErrorDeValidacion("contenido no puede estar vacio.")
    return cassandra_adapter.crear_comentario(partido_id, bloque_horario, usuario_id, usuario_nombre, contenido, clave_idempotencia)
