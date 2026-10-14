# -*- coding: utf-8 -*-
"""
Pruebas de integracion contra la API real, con las 6 bases levantadas
(docker compose up -d) y los datos de scripts/sembrar_datos.sh ya cargados.
No son mocks: pegan contra Mongo/Neo4j/Cassandra/Redis/InfluxDB/IRIS reales,
siguiendo el mismo criterio de los Hitos 4 a 9.

Requiere: la API corriendo en http://localhost:8000 (scripts/iniciar_api.sh).

Uso: pytest tests/integration -v
"""

import os

import httpx
import pytest

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def cliente():
    with httpx.Client(base_url=BASE_URL, timeout=10) as c:
        yield c


# --- RF3 / Mongo -------------------------------------------------------

def test_equipo_existente_devuelve_200(cliente):
    r = cliente.get("/equipos/ARG")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["_id"] == "ARG"
    assert cuerpo["confederacion"] == "CONMEBOL"


def test_equipo_inexistente_devuelve_404_con_formato_comun(cliente):
    r = cliente.get("/equipos/ZZZ")
    assert r.status_code == 404
    error = r.json()["error"]
    assert error["tipo"] == "no_encontrado"
    assert "request_id" in error


def test_confederacion_invalida_devuelve_400(cliente):
    r = cliente.get("/equipos", params={"confederacion": "NO_EXISTE"})
    assert r.status_code == 400
    assert r.json()["error"]["tipo"] == "validacion"


def test_listar_equipos_paginado(cliente):
    r = cliente.get("/equipos", params={"pagina": 1, "tamanio_pagina": 5})
    assert r.status_code == 200
    cuerpo = r.json()
    assert len(cuerpo["items"]) <= 5
    assert cuerpo["total"] >= 64


# --- RF4 / Neo4j --------------------------------------------------------

def test_partido_existente_devuelve_equipos_y_sede(cliente):
    r = cliente.get("/partidos/F2030-006")
    assert r.status_code == 200
    cuerpo = r.json()
    assert {cuerpo["equipo_a"], cuerpo["equipo_b"]} == {"ARG", "ESP"}
    assert cuerpo["sede"] is not None


def test_partido_inexistente_devuelve_404(cliente):
    r = cliente.get("/partidos/F2030-999")
    assert r.status_code == 404


def test_eventos_de_partido_recorren_dos_relaciones(cliente):
    r = cliente.get("/partidos/F2030-006/eventos")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert items[0]["jugador_codigo"] == "ARG-10"


# --- RF5 / Cassandra -----------------------------------------------------

def test_comentarios_de_bloque_existente(cliente):
    r = cliente.get("/partidos/F2030-006/comentarios", params={"bloque_horario": "203006181800"})
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1


def test_bloque_horario_con_formato_invalido_es_400(cliente):
    r = cliente.get("/partidos/F2030-006/comentarios", params={"bloque_horario": "no-es-un-bloque"})
    assert r.status_code == 400


def test_crear_comentario_y_reintento_no_duplica(cliente):
    cuerpo = {
        "usuario_id": "user-test-99",
        "usuario_nombre": "tester",
        "contenido": "comentario de prueba de integracion",
        "clave_idempotencia": "clave-fija-del-test-de-integracion",
    }
    r1 = cliente.post("/partidos/F2030-006/comentarios", params={"bloque_horario": "203006181800"}, json=cuerpo)
    assert r1.status_code == 201
    id1 = r1.json()["comentario_id"]

    r2 = cliente.post("/partidos/F2030-006/comentarios", params={"bloque_horario": "203006181800"}, json=cuerpo)
    assert r2.status_code == 201
    id2 = r2.json()["comentario_id"]

    assert id1 == id2  # RF19: misma clave de idempotencia -> mismo id, no un duplicado


# --- RF6 / Redis ---------------------------------------------------------

def test_sesion_existente_no_expone_token(cliente):
    r = cliente.get("/sesiones/user-00001")
    assert r.status_code == 200
    cuerpo = r.json()
    assert "token" not in cuerpo
    assert cuerpo["rol"] == "fan"


def test_sesion_inexistente_es_404(cliente):
    r = cliente.get("/sesiones/usuario-que-nunca-existio")
    assert r.status_code == 404


def test_cache_hit_y_invalidacion(cliente):
    hit = cliente.get("/partidos/F2030-006/cache")
    assert hit.status_code == 200

    inval = cliente.delete("/partidos/F2030-006/cache")
    assert inval.status_code == 200
    assert inval.json()["habia_valor"] is True

    miss = cliente.get("/partidos/F2030-006/cache")
    assert miss.status_code == 404

    # Idempotencia: invalidar lo ya invalidado no es un error.
    segunda_invalidacion = cliente.delete("/partidos/F2030-006/cache")
    assert segunda_invalidacion.status_code == 200
    assert segunda_invalidacion.json()["habia_valor"] is False


# --- RF7 / InfluxDB --------------------------------------------------------

def test_ventana_de_estadisticas(cliente):
    r = cliente.get(
        "/partidos/F2030-006/estadisticas",
        params={"equipo_id": "ARG", "desde": "2030-06-18T18:00:00Z", "hasta": "2030-06-18T18:02:00Z"},
    )
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1


def test_desde_mayor_a_hasta_es_400(cliente):
    r = cliente.get(
        "/partidos/F2030-006/estadisticas",
        params={"equipo_id": "ARG", "desde": "2030-06-18T18:02:00Z", "hasta": "2030-06-18T18:00:00Z"},
    )
    assert r.status_code == 400


def test_agregacion_incorrecta_para_el_campo_es_400(cliente):
    r = cliente.get(
        "/partidos/F2030-006/estadisticas/agregacion",
        params={
            "equipo_id": "ARG", "desde": "2030-06-18T18:00:00Z", "hasta": "2030-06-18T18:02:00Z",
            "campo": "tiros", "funcion": "avg",  # MAX es la correcta para un contador acumulado
        },
    )
    assert r.status_code == 400


def test_agregacion_correcta(cliente):
    r = cliente.get(
        "/partidos/F2030-006/estadisticas/agregacion",
        params={
            "equipo_id": "ARG", "desde": "2030-06-18T18:00:00Z", "hasta": "2030-06-18T18:02:00Z",
            "campo": "posesion_pct", "funcion": "avg",
        },
    )
    assert r.status_code == 200
    assert r.json()["valor"] is not None


# --- RF8 / IRIS ------------------------------------------------------------

def test_entidad_compleja_existente(cliente):
    r = cliente.get("/partidos/M001/entidad-compleja")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["codigo"] == "M001"
    assert len(cuerpo["eventos"]) >= 1


def test_entidad_compleja_inexistente_es_404(cliente):
    r = cliente.get("/partidos/M999/entidad-compleja")
    assert r.status_code == 404


def test_transicion_de_estado_invalida_es_409(cliente):
    # M001 queda Finalizado despues de Fixture.Demo.Ejecutar(): no puede retroceder.
    r = cliente.patch("/partidos/M001/estado", json={"nuevo_estado": "EnJuego"})
    assert r.status_code == 409
    assert r.json()["error"]["tipo"] == "conflicto"


def test_transicion_al_mismo_estado_es_idempotente(cliente):
    r = cliente.patch("/partidos/M001/estado", json={"nuevo_estado": "Finalizado"})
    assert r.status_code == 200
    assert r.json()["sin_cambios"] is True
