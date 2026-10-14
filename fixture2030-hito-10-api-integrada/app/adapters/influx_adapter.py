# -*- coding: utf-8 -*-
"""
Adaptador de InfluxDB 3 Core (RF7, 5.9). El producto habla HTTP + SQL, no un
cliente de los antiguos v1/v2: se usa `/api/v3/query_sql` directamente.

Respeta el modelo del Hito 8 (`docs/modelo_multidimensional.md`): la tabla
`estadisticas` tiene una muestra (`posesion_pct`, se agrega con AVG) y dos
contadores acumulados (`pases_completados`, `tiros`, se agregan con MAX,
nunca SUM). El adaptador no arma SQL libre: valida partido/equipo/ventana
antes de interpolar, porque esta API HTTP no admite bind parameters.
"""

import re

import httpx

from app.config import settings
from app.errors import DependenciaNoDisponible, ErrorDeValidacion, ErrorInterno

_PATRON_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")

# (campo, agregacion) permitidos -- coincide con la semantica documentada en el Hito 8.
AGREGACIONES_VALIDAS = {
    ("posesion_pct", "avg"),
    ("pases_completados", "max"),
    ("tiros", "max"),
}


def validar_identificador(valor: str, nombre: str) -> str:
    if not _PATRON_ID.match(valor):
        raise ErrorDeValidacion(f"{nombre} invalido: solo letras, numeros, '-' y '_' (recibido: {valor!r}).")
    return valor


def validar_agregacion(campo: str, funcion: str) -> tuple[str, str]:
    if (campo, funcion) not in AGREGACIONES_VALIDAS:
        permitidas = ", ".join(f"{c}:{f}" for c, f in sorted(AGREGACIONES_VALIDAS))
        raise ErrorDeValidacion(
            f"Combinacion campo/agregacion no soportada ({campo}:{funcion}). Permitidas: {permitidas}."
        )
    return campo, funcion


def _consultar(sql: str) -> list[dict]:
    try:
        respuesta = httpx.post(
            f"{settings.influx.url}/api/v3/query_sql",
            headers={"Authorization": f"Bearer {settings.influx.token}"},
            json={"db": settings.influx.database, "q": sql, "format": "json"},
            timeout=settings.influx.timeout_s,
        )
    except httpx.HTTPError as exc:
        raise DependenciaNoDisponible("InfluxDB no respondio a tiempo.", detalle_interno=f"{sql}: {exc!r}") from exc
    if respuesta.status_code >= 500:
        raise DependenciaNoDisponible(
            "InfluxDB devolvio un error de servidor.", detalle_interno=f"{sql}: {respuesta.status_code} {respuesta.text}"
        )
    if respuesta.status_code >= 400:
        raise ErrorInterno(
            "InfluxDB rechazo la consulta generada por la API.",
            detalle_interno=f"{sql}: {respuesta.status_code} {respuesta.text}",
        )
    try:
        return respuesta.json()
    except ValueError as exc:
        raise ErrorInterno("Respuesta de InfluxDB no interpretable.", detalle_interno=str(exc)) from exc


def estadisticas_ventana(partido_id: str, equipo_id: str, desde_iso: str, hasta_iso: str, limite: int) -> list[dict]:
    """PA1 del Hito 8: ventana temporal de un equipo en un partido, sin agregar."""
    sql = (
        "SELECT time, equipo_id, posesion_pct, pases_completados, tiros "
        "FROM estadisticas "
        f"WHERE partido_id = '{partido_id}' AND equipo_id = '{equipo_id}' "
        f"AND time >= '{desde_iso}' AND time < '{hasta_iso}' "
        "ORDER BY time "
        f"LIMIT {limite}"
    )
    return _consultar(sql)


def estadisticas_agregadas(partido_id: str, equipo_id: str, desde_iso: str, hasta_iso: str, campo: str, funcion: str) -> list[dict]:
    """PA3 del Hito 8: agregacion por ventana, solo con la funcion correcta para el campo."""
    sql = (
        f"SELECT equipo_id, {funcion.upper()}({campo}) AS valor "
        "FROM estadisticas "
        f"WHERE partido_id = '{partido_id}' AND equipo_id = '{equipo_id}' "
        f"AND time >= '{desde_iso}' AND time < '{hasta_iso}' "
        "GROUP BY equipo_id"
    )
    return _consultar(sql)


def verificar_conectividad() -> bool:
    try:
        _consultar("SELECT 1 AS ok")
        return True
    except Exception:  # noqa: BLE001
        return False
