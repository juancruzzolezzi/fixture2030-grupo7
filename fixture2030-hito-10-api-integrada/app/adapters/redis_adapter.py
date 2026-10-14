# -*- coding: utf-8 -*-
"""
Adaptador de Redis (RF6, 5.8). Respeta la convencion de claves del Hito 7:
`fixture2030:<dominio>:<id>`. El token de sesion nunca se expone (vive en el
Hash pero no se devuelve en la respuesta, tal como documenta el Hito 7).
"""

import redis
from redis.exceptions import RedisError

from app.config import settings
from app.errors import DependenciaNoDisponible, ErrorInterno

_cliente: redis.Redis | None = None


def _activo() -> redis.Redis:
    global _cliente
    if _cliente is None:
        _cliente = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.puerto,
            db=settings.redis.db,
            socket_connect_timeout=settings.redis.timeout_s,
            socket_timeout=settings.redis.timeout_s,
            decode_responses=True,
        )
    return _cliente


def _traducir(exc: Exception, contexto: str):
    if isinstance(exc, RedisError):
        raise DependenciaNoDisponible(
            "Redis no respondio a tiempo.",
            detalle_interno=f"{contexto}: {exc!r}",
        ) from exc
    raise ErrorInterno("Fallo inesperado consultando Redis.", detalle_interno=f"{contexto}: {exc!r}") from exc


def obtener_sesion(usuario_id: str) -> dict | None:
    """Ausente o expirada se ven igual desde Redis (la clave ya no esta): se
    devuelve None en los dos casos, tal como advierte RF6."""
    clave = f"fixture2030:sesion:{usuario_id}"
    try:
        datos = _activo().hgetall(clave)
        if not datos:
            return None
        ttl = _activo().ttl(clave)
        datos.pop("token", None)  # nunca se expone, aunque existiera (Hito 7, seguridad local)
        datos["segundos_restantes"] = ttl if ttl and ttl > 0 else None
        return datos
    except Exception as exc:  # noqa: BLE001
        _traducir(exc, f"obtener_sesion({usuario_id})")


def obtener_cache_partido(partido_id: str) -> str | None:
    clave = f"fixture2030:cache:partido:{partido_id}"
    try:
        return _activo().get(clave)
    except Exception as exc:  # noqa: BLE001
        _traducir(exc, f"obtener_cache_partido({partido_id})")


def invalidar_cache_partido(partido_id: str) -> bool:
    """True si habia algo para borrar, False si ya estaba vacio (idempotente, RF19)."""
    clave = f"fixture2030:cache:partido:{partido_id}"
    try:
        return _activo().delete(clave) > 0
    except Exception as exc:  # noqa: BLE001
        _traducir(exc, f"invalidar_cache_partido({partido_id})")


def verificar_conectividad() -> bool:
    try:
        return bool(_activo().ping())
    except Exception:  # noqa: BLE001
        return False
