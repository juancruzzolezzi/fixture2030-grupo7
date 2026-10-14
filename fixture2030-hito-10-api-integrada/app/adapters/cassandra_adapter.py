# -*- coding: utf-8 -*-
"""
Adaptador de Cassandra (RF5, 5.7). Respeta la tabla y la clave de particion
del Hito 6: `comentarios_por_bloque`, particionada por (partido_id,
bloque_horario). Nunca se consulta sin ambos componentes de la particion
(evitar ALLOW FILTERING es una restriccion explicita de la consigna).
"""

import uuid
from datetime import datetime, timezone

from cassandra.cluster import Cluster, NoHostAvailable
from cassandra.query import SimpleStatement

from app.config import settings
from app.errors import DependenciaNoDisponible, ErrorInterno

_session = None

NAMESPACE_API = uuid.UUID("6ea1f0c0-0000-4000-8000-000000000010")  # fijo: ids deterministicos para reintentos (RF19)


def _sesion_activa():
    global _session
    if _session is None:
        cluster = Cluster(list(settings.cassandra.hosts), port=settings.cassandra.puerto)
        _session = cluster.connect(settings.cassandra.keyspace)
    return _session


def _traducir(exc: Exception, contexto: str):
    if isinstance(exc, NoHostAvailable):
        raise DependenciaNoDisponible(
            "Cassandra no respondio a tiempo.",
            detalle_interno=f"{contexto}: {exc!r}",
        ) from exc
    raise ErrorInterno("Fallo inesperado consultando Cassandra.", detalle_interno=f"{contexto}: {exc!r}") from exc


def listar_comentarios(partido_id: str, bloque_horario: str, limite: int) -> list[dict]:
    """Lectura paginada por particion completa (RF5, RNF12/RNF13): nunca una
    particion sin su bloque. Ya viene ordenado por la CLUSTERING ORDER de la tabla."""
    consulta = SimpleStatement(
        "SELECT creado_en, comentario_id, usuario_id, usuario_nombre, contenido, estado, likes "
        "FROM comentarios_por_bloque WHERE partido_id = %s AND bloque_horario = %s LIMIT %s",
        fetch_size=limite,
    )
    try:
        filas = _sesion_activa().execute(consulta, (partido_id, bloque_horario, limite))
        resultado = []
        for f in filas:
            fila = dict(f._asdict())
            fila["comentario_id"] = str(fila["comentario_id"])  # uuid.UUID -> str para el schema de salida
            resultado.append(fila)
        return resultado
    except Exception as exc:  # noqa: BLE001
        _traducir(exc, f"listar_comentarios({partido_id},{bloque_horario})")


def crear_comentario(partido_id: str, bloque_horario: str, usuario_id: str, usuario_nombre: str, contenido: str, clave_idempotencia: str) -> dict:
    """Creacion respetando la particion de diseño (RF5). El id del comentario se
    deriva de una clave de idempotencia que aporta el consumidor: reintentar
    la misma request escribe la misma fila, no duplica (RF19)."""
    comentario_id = uuid.uuid5(NAMESPACE_API, f"{partido_id}|{bloque_horario}|{clave_idempotencia}")
    creado_en = datetime.now(timezone.utc)
    try:
        _sesion_activa().execute(
            "INSERT INTO comentarios_por_bloque "
            "(partido_id, bloque_horario, creado_en, comentario_id, usuario_id, usuario_nombre, contenido, estado, likes, reportes) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (partido_id, bloque_horario, creado_en, comentario_id, usuario_id, usuario_nombre, contenido, "visible", 0, 0),
        )
        _sesion_activa().execute(
            "INSERT INTO comentarios_por_usuario (usuario_id, creado_en, comentario_id, partido_id, contenido) "
            "VALUES (%s, %s, %s, %s, %s)",
            (usuario_id, creado_en, comentario_id, partido_id, contenido),
        )
    except Exception as exc:  # noqa: BLE001
        _traducir(exc, f"crear_comentario({partido_id},{bloque_horario})")
    return {
        "comentario_id": str(comentario_id),
        "partido_id": partido_id,
        "bloque_horario": bloque_horario,
        "creado_en": creado_en,
        "usuario_id": usuario_id,
        "usuario_nombre": usuario_nombre,
        "contenido": contenido,
        "estado": "visible",
        "likes": 0,
    }


def verificar_conectividad() -> bool:
    try:
        _sesion_activa().execute("SELECT release_version FROM system.local")
        return True
    except Exception:  # noqa: BLE001
        return False
