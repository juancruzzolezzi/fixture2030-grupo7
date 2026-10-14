# -*- coding: utf-8 -*-
"""Rutas de Comentarios (Cassandra, RF5)."""

from fastapi import APIRouter, Query, status

from app.schemas.comentarios import ComentarioCreado, ListaComentarios, NuevoComentarioRequest
from app.schemas.common import RespuestaError
from app.services import comentarios_service

router = APIRouter(prefix="/partidos/{codigo}/comentarios", tags=["Comentarios (Cassandra)"])


@router.get(
    "",
    response_model=ListaComentarios,
    summary="Comentarios de un partido en un bloque de 5 minutos (lectura por particion completa)",
    responses={400: {"model": RespuestaError}},
)
def listar_comentarios(
    codigo: str,
    bloque_horario: str = Query(..., description="AAAAMMDDHHmm, el mismo formato del Hito 6"),
    limite: int = Query(20, ge=1, le=100),
):
    items = comentarios_service.listar_comentarios(codigo, bloque_horario, limite)
    return ListaComentarios(partido_id=codigo, bloque_horario=bloque_horario, items=items)


@router.post(
    "",
    response_model=ComentarioCreado,
    status_code=status.HTTP_201_CREATED,
    summary="Publicar un comentario, respetando la particion (partido_id, bloque_horario)",
    responses={400: {"model": RespuestaError}},
)
def crear_comentario(
    codigo: str,
    cuerpo: NuevoComentarioRequest,
    bloque_horario: str = Query(..., description="Bloque al que pertenece el comentario, AAAAMMDDHHmm"),
):
    resultado = comentarios_service.crear_comentario(
        codigo, bloque_horario, cuerpo.usuario_id, cuerpo.usuario_nombre, cuerpo.contenido, cuerpo.clave_idempotencia
    )
    return ComentarioCreado(**resultado)
