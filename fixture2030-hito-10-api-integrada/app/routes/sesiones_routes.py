# -*- coding: utf-8 -*-
"""Rutas de Sesiones y Cache (Redis, RF6)."""

from fastapi import APIRouter, status

from app.schemas.common import RespuestaError
from app.schemas.sesiones import CachePartido, InvalidacionCacheResponse, Sesion
from app.services import sesiones_service

router = APIRouter(tags=["Sesiones y cache (Redis)"])


@router.get(
    "/sesiones/{usuario_id}",
    response_model=Sesion,
    summary="Estado de la sesion de un usuario (sin exponer el token)",
    responses={404: {"model": RespuestaError}},
)
def obtener_sesion(usuario_id: str):
    return sesiones_service.obtener_sesion(usuario_id)


@router.get(
    "/partidos/{codigo}/cache",
    response_model=CachePartido,
    summary="Contenido cacheado de un partido (404 = cache miss, no un error)",
    responses={404: {"model": RespuestaError}},
)
def obtener_cache_partido(codigo: str):
    return sesiones_service.obtener_cache_partido(codigo)


@router.delete(
    "/partidos/{codigo}/cache",
    response_model=InvalidacionCacheResponse,
    status_code=status.HTTP_200_OK,
    summary="Invalidar la cache de un partido (idempotente: invalidar dos veces no es un error)",
)
def invalidar_cache_partido(codigo: str):
    return sesiones_service.invalidar_cache_partido(codigo)
