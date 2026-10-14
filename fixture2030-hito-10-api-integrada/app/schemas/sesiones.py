# -*- coding: utf-8 -*-
"""Schemas del recurso Sesiones/Caché (Redis, Hito 7)."""

from pydantic import BaseModel


class Sesion(BaseModel):
    usuario_id: str
    rol: str
    estado: str
    ultimo_acceso: str | None = None
    paginas_vistas: int | None = None
    segundos_restantes: int | None = None


class CachePartido(BaseModel):
    partido_id: str
    contenido: str


class InvalidacionCacheResponse(BaseModel):
    partido_id: str
    habia_valor: bool
