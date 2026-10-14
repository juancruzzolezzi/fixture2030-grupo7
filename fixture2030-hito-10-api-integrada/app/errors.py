# -*- coding: utf-8 -*-
"""
Taxonomia de errores de la API (RF11, RF12, RNF4).

Los adaptadores levantan estas excepciones; main.py las traduce a una
respuesta HTTP con el mismo formato siempre:

    {"error": {"tipo": "...", "mensaje": "...", "request_id": "..."}}

El detalle tecnico (excepcion original del driver, query, stack) nunca sale
en la respuesta: va solo al log, identificado por el mismo request_id
(RF12, RNF7, RNF10).
"""

import logging

logger = logging.getLogger("fixture2030.api")


class ErrorDeAplicacion(Exception):
    """Base de todos los errores que la API sabe traducir a HTTP."""

    status_code = 500
    tipo = "error_interno"

    def __init__(self, mensaje: str, *, detalle_interno: str | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalle_interno = detalle_interno


class ErrorDeValidacion(ErrorDeAplicacion):
    """Parametro de ruta, query o cuerpo invalido. No se llega a consultar la fuente (RNF3)."""

    status_code = 400
    tipo = "validacion"


class RecursoNoEncontrado(ErrorDeAplicacion):
    """La fuente respondio, pero el recurso pedido no existe."""

    status_code = 404
    tipo = "no_encontrado"


class ConflictoDeNegocio(ErrorDeAplicacion):
    """La operacion es valida sintacticamente pero el estado actual no la permite
    (ej. transicion de estado ilegal en IRIS, o pisar una fila que no corresponde)."""

    status_code = 409
    tipo = "conflicto"


class DependenciaNoDisponible(ErrorDeAplicacion):
    """La fuente de datos no respondio (caida, timeout, red). Nunca se traduce a
    un 200 vacio: la consigna lo prohibe explicitamente."""

    status_code = 503
    tipo = "dependencia_no_disponible"


class ErrorInterno(ErrorDeAplicacion):
    """Cualquier otra falla no prevista. El mensaje al cliente es generico a
    proposito; el detalle_interno queda solo en el log."""

    status_code = 500
    tipo = "error_interno"
