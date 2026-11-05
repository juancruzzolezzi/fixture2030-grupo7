# -*- coding: utf-8 -*-
"""
Hito 13: GET /metrics. Corre contra la API real, igual que las demas pruebas.
Requiere la API en el puerto 8000. MongoDB tiene que estar levantada y sembrada.

Uso: pytest tests/integration/test_metricas.py -v
"""

import httpx

BASE_URL = "http://localhost:8000"


def _metricas() -> str:
    r = httpx.get(f"{BASE_URL}/metrics", timeout=15)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    return r.text


def test_expone_la_salud_de_las_seis_bases():
    texto = _metricas()
    for base in ("mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris"):
        assert f'database_up{{database="{base}"}}' in texto


def test_cuenta_la_request_con_el_template_de_la_ruta():
    assert httpx.get(f"{BASE_URL}/equipos/ARG", timeout=10).status_code == 200
    texto = _metricas()
    assert 'api_http_requests_total{clase="2xx",metodo="GET",ruta="/equipos/{codigo}",status="200"}' in texto
    assert 'ruta="/equipos/ARG"' not in texto  # un codigo no crea una serie nueva


def test_un_404_no_cuenta_como_falla_de_la_base():
    assert httpx.get(f"{BASE_URL}/equipos/ZZZ", timeout=10).status_code == 404
    texto = _metricas()
    assert 'api_http_requests_total{clase="4xx",metodo="GET",ruta="/equipos/{codigo}",status="404"}' in texto
    assert 'database_errors_total{database="mongodb"' not in texto


def test_las_rutas_de_operacion_no_cuentan_como_trafico():
    httpx.get(f"{BASE_URL}/salud/vivo", timeout=10)
    texto = _metricas()
    assert 'ruta="/metrics"' not in texto
    assert 'ruta="/salud' not in texto
