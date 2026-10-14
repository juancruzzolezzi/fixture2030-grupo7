# -*- coding: utf-8 -*-
"""
Adaptador de IRIS (RF8, 5.10). Usa el Native SDK (`iris.connect` +
`createIRIS`) para invocar `Fixture.ApiSupport`, la unica clase que agrega
este hito -- las clases de dominio del Hito 9 (Persona/Jugador/Arbitro/
Tecnico/Partido/Evento) no se tocan. Toda la validacion de transiciones y la
navegacion de relaciones siguen pasando por los metodos encapsulados del
objeto, nunca por SQL directo contra las tablas (RNF5, consigna 5.10).
"""

import json

import iris

from app.config import settings
from app.errors import ConflictoDeNegocio, DependenciaNoDisponible, ErrorInterno

_conexion = None
_irispy = None


def _activo():
    global _conexion, _irispy
    if _irispy is None:
        _conexion = iris.connect(
            hostname=settings.iris.hostname,
            port=settings.iris.puerto,
            namespace=settings.iris.namespace,
            username=settings.iris.usuario,
            password=settings.iris.password,
        )
        _irispy = iris.createIRIS(_conexion)
    return _irispy


def _traducir(exc: Exception, contexto: str):
    raise DependenciaNoDisponible("IRIS no respondio a tiempo.", detalle_interno=f"{contexto}: {exc!r}") from exc


def obtener_partido_detalle(codigo: str) -> dict | None:
    try:
        crudo = _activo().classMethodValue("Fixture.ApiSupport", "ObtenerPartidoDetalle", codigo)
    except Exception as exc:  # noqa: BLE001
        _traducir(exc, f"obtener_partido_detalle({codigo})")
    try:
        datos = json.loads(crudo)
    except ValueError as exc:
        raise ErrorInterno("IRIS devolvio un JSON no interpretable.", detalle_interno=str(exc)) from exc
    if not datos.get("encontrado"):
        return None
    return datos


def cambiar_estado_partido(codigo: str, nuevo_estado: str) -> dict:
    try:
        crudo = _activo().classMethodValue("Fixture.ApiSupport", "CambiarEstadoPartido", codigo, nuevo_estado)
    except Exception as exc:  # noqa: BLE001
        _traducir(exc, f"cambiar_estado_partido({codigo},{nuevo_estado})")
    try:
        datos = json.loads(crudo)
    except ValueError as exc:
        raise ErrorInterno("IRIS devolvio un JSON no interpretable.", detalle_interno=str(exc)) from exc
    if not datos.get("ok"):
        motivo = datos.get("motivo")
        if motivo == "no_existe":
            return {"existe": False}
        raise ConflictoDeNegocio(
            f"Transicion de estado invalida (sigue en {datos.get('estado_actual')!r}).",
            detalle_interno=str(datos),
        )
    datos["existe"] = True
    return datos


def verificar_conectividad() -> bool:
    try:
        _activo().classMethodValue("%SYSTEM.Version", "GetVersion")
        return True
    except Exception:  # noqa: BLE001
        return False
