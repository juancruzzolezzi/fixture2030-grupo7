# -*- coding: utf-8 -*-
"""Caso de uso: sesiones y cache via Redis (RF6)."""

from app.adapters import redis_adapter
from app.errors import ErrorDeValidacion, RecursoNoEncontrado


def obtener_sesion(usuario_id: str) -> dict:
    if not usuario_id:
        raise ErrorDeValidacion("usuario_id invalido.")
    sesion = redis_adapter.obtener_sesion(usuario_id)
    if sesion is None:
        # Ausente o expirada se ven igual desde Redis (RF6): un solo 404,
        # con un mensaje que no promete distinguir lo que la fuente no distingue.
        raise RecursoNoEncontrado(f"No hay una sesion vigente para {usuario_id!r} (no existe o expiro).")
    sesion["usuario_id"] = usuario_id
    return sesion


def obtener_cache_partido(partido_id: str) -> dict:
    if not partido_id:
        raise ErrorDeValidacion("partido_id invalido.")
    contenido = redis_adapter.obtener_cache_partido(partido_id)
    if contenido is None:
        raise RecursoNoEncontrado(f"No hay cache vigente para el partido {partido_id!r} (cache miss).")
    return {"partido_id": partido_id, "contenido": contenido}


def invalidar_cache_partido(partido_id: str) -> dict:
    if not partido_id:
        raise ErrorDeValidacion("partido_id invalido.")
    habia_valor = redis_adapter.invalidar_cache_partido(partido_id)
    return {"partido_id": partido_id, "habia_valor": habia_valor}
