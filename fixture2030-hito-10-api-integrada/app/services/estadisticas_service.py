# -*- coding: utf-8 -*-
"""Caso de uso: estadisticas temporales via InfluxDB (RF7). Toda fecha se
valida ANTES de tocar la base (RNF3, nota "La validacion debe ocurrir antes
de consultar" de la consigna)."""

from datetime import datetime

from app.adapters import influx_adapter
from app.errors import ErrorDeValidacion

LIMITE_MAXIMO = 500


def _parsear_fecha(valor: str, nombre: str) -> datetime:
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ErrorDeValidacion(f"{nombre} invalido, se espera ISO 8601 (recibido: {valor!r}).") from exc


def _validar_ventana(partido_id: str, equipo_id: str, desde: str, hasta: str) -> None:
    influx_adapter.validar_identificador(partido_id, "partido_id")
    influx_adapter.validar_identificador(equipo_id, "equipo_id")
    f_desde = _parsear_fecha(desde, "desde")
    f_hasta = _parsear_fecha(hasta, "hasta")
    if f_desde >= f_hasta:
        raise ErrorDeValidacion("desde debe ser anterior a hasta.")


def ventana(partido_id: str, equipo_id: str, desde: str, hasta: str, limite: int) -> list[dict]:
    _validar_ventana(partido_id, equipo_id, desde, hasta)
    if not (1 <= limite <= LIMITE_MAXIMO):
        raise ErrorDeValidacion(f"limite debe estar entre 1 y {LIMITE_MAXIMO}.")
    return influx_adapter.estadisticas_ventana(partido_id, equipo_id, desde, hasta, limite)


def agregacion(partido_id: str, equipo_id: str, desde: str, hasta: str, campo: str, funcion: str) -> dict | None:
    _validar_ventana(partido_id, equipo_id, desde, hasta)
    influx_adapter.validar_agregacion(campo, funcion)
    filas = influx_adapter.estadisticas_agregadas(partido_id, equipo_id, desde, hasta, campo, funcion)
    return filas[0] if filas else None
