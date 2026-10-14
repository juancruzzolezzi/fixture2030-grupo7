# -*- coding: utf-8 -*-
"""
Adaptador de MongoDB (RF3, 5.5). Encapsula el driver pymongo: nadie fuera de
este archivo importa pymongo ni conoce el nombre de las colecciones (RNF5).

Reutiliza el modelo documental del Hito 4: colecciones `equipos` y
`jugadores`, _id = codigo de negocio (p.ej. "ARG", "ARG-10").
"""

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.config import settings
from app.errors import DependenciaNoDisponible, ErrorInterno

_client: MongoClient | None = None


def _db():
    global _client
    if _client is None:
        _client = MongoClient(
            settings.mongo.uri,
            serverSelectionTimeoutMS=settings.mongo.timeout_ms,
            connectTimeoutMS=settings.mongo.timeout_ms,
        )
    return _client[settings.mongo.db]


def _traducir(exc: Exception, contexto: str):
    if isinstance(exc, PyMongoError):
        raise DependenciaNoDisponible(
            "MongoDB no respondio a tiempo.",
            detalle_interno=f"{contexto}: {exc!r}",
        ) from exc
    raise ErrorInterno("Fallo inesperado consultando MongoDB.", detalle_interno=f"{contexto}: {exc!r}") from exc


def obtener_equipo(codigo: str) -> dict | None:
    """Recuperacion por codigo (RNF13: patron de acceso por clave, equivalente al Hito 4)."""
    try:
        return _db().equipos.find_one({"_id": codigo})
    except Exception as exc:  # noqa: BLE001
        _traducir(exc, f"obtener_equipo({codigo})")


def listar_equipos(confederacion: str | None, pagina: int, tamanio_pagina: int) -> tuple[list[dict], int]:
    """Filtro + paginado (RNF12): nunca un find() sin limit."""
    filtro = {"confederacion": confederacion} if confederacion else {}
    try:
        coleccion = _db().equipos
        total = coleccion.count_documents(filtro)
        salto = (pagina - 1) * tamanio_pagina
        cursor = coleccion.find(filtro).sort("_id", 1).skip(salto).limit(tamanio_pagina)
        return list(cursor), total
    except Exception as exc:  # noqa: BLE001
        _traducir(exc, "listar_equipos")


def obtener_jugador(codigo: str) -> dict | None:
    try:
        return _db().jugadores.find_one({"_id": codigo})
    except Exception as exc:  # noqa: BLE001
        _traducir(exc, f"obtener_jugador({codigo})")


def listar_jugadores_de_equipo(equipo_id: str, posicion: str | None, pagina: int, tamanio_pagina: int) -> tuple[list[dict], int]:
    filtro: dict = {"equipo_id": equipo_id}
    if posicion:
        filtro["posicion"] = posicion
    try:
        coleccion = _db().jugadores
        total = coleccion.count_documents(filtro)
        salto = (pagina - 1) * tamanio_pagina
        cursor = (
            coleccion.find(filtro, {"_id": 1, "nombre": 1, "apellido": 1, "dorsal": 1, "posicion": 1})
            .sort("dorsal", 1)
            .skip(salto)
            .limit(tamanio_pagina)
        )
        return list(cursor), total
    except Exception as exc:  # noqa: BLE001
        _traducir(exc, f"listar_jugadores_de_equipo({equipo_id})")


def verificar_conectividad() -> bool:
    try:
        _db().client.admin.command("ping")
        return True
    except Exception:  # noqa: BLE001
        return False
