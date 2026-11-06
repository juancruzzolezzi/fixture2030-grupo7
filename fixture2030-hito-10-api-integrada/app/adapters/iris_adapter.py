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
import threading

import iris

from app.config import settings
from app.errors import ConflictoDeNegocio, DependenciaNoDisponible, ErrorInterno, TiempoDeEsperaAgotado

_conexion = None
_irispy = None
# Hito 13: hay una sola conexion a IRIS y la API atiende en varios hilos. Las llamadas
# pasan de a una; si no se consigue el turno a tiempo, responde 504 y no traba al resto de la API.
_turno = threading.Lock()


class _ConexionOcupada(Exception):
    pass


def _activo():
    global _conexion, _irispy
    if _irispy is None:
        _conexion = iris.connect(
            hostname=settings.iris.hostname,
            port=settings.iris.puerto,
            namespace=settings.iris.namespace,
            username=settings.iris.usuario,
            password=settings.iris.password,
            timeout=int(settings.iris.timeout_s),  # sin esto el SDK espera 10 s
            sharedmemory=False,  # con "localhost" intenta memoria compartida, que no existe contra un contenedor
        )
        _irispy = iris.createIRIS(_conexion)
    return _irispy


def _llamar(clase: str, metodo: str, *argumentos):
    if not _turno.acquire(timeout=settings.iris.timeout_s):
        raise _ConexionOcupada()
    try:
        return _activo().classMethodValue(clase, metodo, *argumentos)
    finally:
        _turno.release()


def _traducir(exc: Exception, contexto: str):
    if isinstance(exc, _ConexionOcupada):  # la conexion sigue en uso: no se descarta
        raise TiempoDeEsperaAgotado("IRIS no respondio a tiempo.", detalle_interno=f"{contexto}: conexion ocupada") from exc
    # Hito 11: si IRIS se reinicia, la conexion guardada queda muerta y la API
    # respondia 503 para siempre (hasta reiniciar la API). Ahora se descarta y
    # la proxima request vuelve a conectar.
    global _conexion, _irispy
    _conexion, _irispy = None, None
    raise DependenciaNoDisponible("IRIS no esta disponible.", detalle_interno=f"{contexto}: {exc!r}") from exc


def obtener_partido_detalle(codigo: str) -> dict | None:
    try:
        crudo = _llamar("Fixture.ApiSupport", "ObtenerPartidoDetalle", codigo)
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
        crudo = _llamar("Fixture.ApiSupport", "CambiarEstadoPartido", codigo, nuevo_estado)
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
    global _conexion, _irispy
    try:
        _llamar("%SYSTEM.Version", "GetVersion")
        return True
    except _ConexionOcupada:
        return False
    except Exception:  # noqa: BLE001
        _conexion, _irispy = None, None  # que el proximo intento reconecte
        return False
