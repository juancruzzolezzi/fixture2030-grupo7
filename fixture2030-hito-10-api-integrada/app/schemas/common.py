# -*- coding: utf-8 -*-
"""Schemas comunes a toda la API: formato de error unico (RF12) y paginado (RNF12)."""

from pydantic import BaseModel, Field


class DetalleError(BaseModel):
    tipo: str = Field(..., description="Categoria del error: validacion, no_encontrado, conflicto, dependencia_no_disponible, error_interno")
    mensaje: str = Field(..., description="Explicacion segura para el consumidor, sin detalles tecnicos")
    request_id: str = Field(..., description="Identificador para correlacionar con los logs de la API y del adaptador")


class RespuestaError(BaseModel):
    error: DetalleError


class Paginado(BaseModel):
    pagina: int = Field(..., ge=1)
    tamanio_pagina: int = Field(..., ge=1)
    total: int | None = Field(None, description="Cuando la fuente puede calcularlo sin costo extra")
