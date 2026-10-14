# -*- coding: utf-8 -*-
"""
Adaptador de Neo4j (RF4, 5.6). Cypher parametrizado unicamente: nunca se
arma una sentencia concatenando texto recibido del consumidor (restriccion
"Diseño" de la consigna).

Reutiliza el modelo del Hito 5: (Jugador)-[:PERTENECE_A]->(Equipo),
(Equipo)-[:DISPUTA]->(Partido)-[:SE_JUEGA_EN]->(Sede), y
(Jugador)-[:PROTAGONIZA]->(Evento)-[:OCURRE_EN]->(Partido).
"""

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.config import settings
from app.errors import DependenciaNoDisponible, ErrorInterno

_driver = None


def _driver_activo():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j.uri,
            auth=(settings.neo4j.usuario, settings.neo4j.password),
            connection_timeout=settings.neo4j.timeout_s,
        )
    return _driver


def _traducir(exc: Exception, contexto: str):
    if isinstance(exc, (ServiceUnavailable, Neo4jError)):
        raise DependenciaNoDisponible(
            "Neo4j no respondio a tiempo.",
            detalle_interno=f"{contexto}: {exc!r}",
        ) from exc
    raise ErrorInterno("Fallo inesperado consultando Neo4j.", detalle_interno=f"{contexto}: {exc!r}") from exc


def obtener_partido(codigo: str) -> dict | None:
    """Partido + los dos equipos que lo disputan + sede (RNF13: un salto por relacion)."""
    consulta = """
    MATCH (a:Equipo)-[ra:DISPUTA]->(p:Partido {codigo: $codigo})<-[rb:DISPUTA]-(b:Equipo)
    WHERE ra.condicion = 'A' AND rb.condicion = 'B'
    OPTIONAL MATCH (p)-[:SE_JUEGA_EN]->(s:Sede)
    RETURN p.codigo AS codigo, p.fecha AS fecha, p.fase AS fase,
           a.codigo AS equipo_a, a.nombre AS equipo_a_nombre,
           b.codigo AS equipo_b, b.nombre AS equipo_b_nombre,
           s.nombre AS sede, s.ciudad AS sede_ciudad
    """
    try:
        with _driver_activo().session() as sesion:
            registro = sesion.run(consulta, codigo=codigo).single()
            if registro is None:
                return None
            datos = dict(registro)
            if datos.get("fecha") is not None:
                datos["fecha"] = str(datos["fecha"])  # neo4j.time.Date -> "AAAA-MM-DD" para el schema de salida
            return datos
    except Exception as exc:  # noqa: BLE001
        _traducir(exc, f"obtener_partido({codigo})")


def listar_eventos_de_partido(codigo: str, limite: int) -> list[dict]:
    """Recorrido de dos relaciones consecutivas (RF4): partido<-ocurre_en-evento-protagoniza-jugador."""
    consulta = """
    MATCH (p:Partido {codigo: $codigo})<-[:OCURRE_EN]-(ev:Evento)<-[:PROTAGONIZA]-(j:Jugador)
    RETURN ev.codigo AS codigo, ev.tipo AS tipo, ev.minuto AS minuto,
           j.codigo AS jugador_codigo, j.nombre AS jugador_nombre, j.apellido AS jugador_apellido
    ORDER BY ev.minuto ASC
    LIMIT $limite
    """
    try:
        with _driver_activo().session() as sesion:
            return [dict(r) for r in sesion.run(consulta, codigo=codigo, limite=limite)]
    except Exception as exc:  # noqa: BLE001
        _traducir(exc, f"listar_eventos_de_partido({codigo})")


def existe_partido(codigo: str) -> bool:
    consulta = "MATCH (p:Partido {codigo: $codigo}) RETURN count(p) AS c"
    try:
        with _driver_activo().session() as sesion:
            return sesion.run(consulta, codigo=codigo).single()["c"] > 0
    except Exception as exc:  # noqa: BLE001
        _traducir(exc, f"existe_partido({codigo})")


def verificar_conectividad() -> bool:
    try:
        _driver_activo().verify_connectivity()
        return True
    except Exception:  # noqa: BLE001
        return False
