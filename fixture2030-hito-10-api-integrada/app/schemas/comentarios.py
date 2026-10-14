# -*- coding: utf-8 -*-
"""Schemas del recurso Comentarios (Cassandra, Hito 6)."""

from datetime import datetime

from pydantic import BaseModel, Field


class Comentario(BaseModel):
    creado_en: datetime
    comentario_id: str
    usuario_id: str
    usuario_nombre: str
    contenido: str
    estado: str
    likes: int


class ListaComentarios(BaseModel):
    partido_id: str
    bloque_horario: str
    items: list[Comentario]


class NuevoComentarioRequest(BaseModel):
    usuario_id: str = Field(..., min_length=1, max_length=32)
    usuario_nombre: str = Field(..., min_length=1, max_length=64)
    contenido: str = Field(..., min_length=1, max_length=280)
    clave_idempotencia: str = Field(
        ..., min_length=1, max_length=64,
        description="Provista por el cliente (p.ej. un uuid generado en el dispositivo). "
                    "Reintentar la misma request con la misma clave no duplica el comentario (RF19).",
    )


class ComentarioCreado(BaseModel):
    comentario_id: str
    partido_id: str
    bloque_horario: str
    creado_en: datetime
    usuario_id: str
    usuario_nombre: str
    contenido: str
    estado: str
    likes: int
