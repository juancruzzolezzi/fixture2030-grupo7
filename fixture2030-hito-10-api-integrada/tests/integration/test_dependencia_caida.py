# -*- coding: utf-8 -*-
"""
RF15: "una dependencia detenida o inaccesible". Esta prueba para de verdad
el contenedor de Redis, confirma el 503, y lo vuelve a levantar -- no
simula la caida con un mock, la provoca contra la infraestructura real.

Requiere: docker compose (de esta carpeta) corriendo, y la API ya arriba
apuntando a REDIS_HOST/REDIS_PORT de esa misma instancia.

Uso: pytest tests/integration/test_dependencia_caida.py -v -s
"""

import subprocess
import time

import httpx
import pytest

BASE_URL = "http://localhost:8000"
SERVICIO = "redis"


def _docker_compose(*args):
    subprocess.run(["docker", "compose", *args], cwd=__file__.rsplit("/tests/", 1)[0], check=True, capture_output=True)


@pytest.fixture
def redis_apagado():
    _docker_compose("stop", SERVICIO)
    time.sleep(1)
    try:
        yield
    finally:
        _docker_compose("start", SERVICIO)
        # Esperar a que vuelva a aceptar conexiones antes de devolver el control.
        for _ in range(30):
            try:
                r = httpx.get(f"{BASE_URL}/sesiones/user-00001", timeout=2)
                if r.status_code in (200, 404):
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)


def test_redis_caido_devuelve_503_no_200_vacio(redis_apagado):
    with httpx.Client(base_url=BASE_URL, timeout=5) as cliente:
        r = cliente.get("/sesiones/user-00001")
    assert r.status_code == 503
    error = r.json()["error"]
    assert error["tipo"] == "dependencia_no_disponible"
    # Decir "Redis" es un mensaje seguro (nombra el producto, no filtra nada).
    # Lo que no debe aparecer es el detalle tecnico: la excepcion real de
    # redis-py, con su traceback o el texto de conexion, queda solo en el log.
    assert "connectionerror" not in error["mensaje"].lower()
    assert "traceback" not in error["mensaje"].lower()
    assert "errno" not in error["mensaje"].lower()
