# -*- coding: utf-8 -*-
"""Hito 13 - lo que comparten los scripts: rutas, consultas a Prometheus, version
del codigo, datos del entorno y control de secretos en la evidencia."""

import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

HITO13 = Path(__file__).resolve().parent.parent
HITO10 = HITO13.parent / "fixture2030-hito-10-api-integrada"
EVIDENCIA = Path(os.environ.get("EVIDENCIA_DIR", HITO13 / "evidencia"))
PROMETHEUS = os.environ.get("PROMETHEUS_URL", "http://127.0.0.1:9090")
GRAFANA = os.environ.get("GRAFANA_URL", "http://127.0.0.1:3000")
API = os.environ.get("API_URL", "http://127.0.0.1:8000")
IMAGENES = ("fixture2030-prometheus", "fixture2030-grafana", "fixture2030-node-exporter",
            "fixture2030-redis-exporter", "fixture2030-mongodb-exporter", "h10-mongodb", "h10-neo4j",
            "h10-cassandra", "h10-redis", "h10-influxdb", "h10-iris")


def ahora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _comando(*args, cwd=None) -> str:
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=20)
        return r.stdout.rstrip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def encabezado(titulo: str) -> list:
    """Fecha, commit y entorno: toda evidencia queda vinculada a una ejecucion (RNF2)."""
    commit = _comando("git", "rev-parse", "--short", "HEAD", cwd=HITO13) or "desconocido"
    cambios = _comando("git", "status", "--porcelain", "--", "../fixture2030-hito-10-api-integrada/app",
                       "prometheus.yml", "prometheus", "grafana", "scripts", cwd=HITO13)
    imagenes = []
    for contenedor in IMAGENES:
        imagen = _comando("docker", "inspect", contenedor, "--format", "{{.Config.Image}} {{.Image}}")
        if imagen:
            nombre, digest = imagen.split(" ", 1)
            imagenes.append(f"{contenedor}={nombre}@{digest.replace('sha256:', '')[:12]}")
    lineas = [
        titulo,
        f"Fecha: {ahora()} | commit: {commit} | archivos sin commitear: {len(cambios.splitlines())}",
        f"Entorno: {platform.system()} {platform.release()}, {os.cpu_count()} CPU logicas, Python {platform.python_version()}",
        "Imagenes: " + (", ".join(imagenes) if imagenes else "no disponible (docker no respondio)"),
    ]
    nota = os.environ.get("NOTA_ENTORNO")
    if nota:
        lineas.append(f"Nota del entorno: {nota}")
    return lineas


def consultar(expr: str, momento: float | None = None) -> list:
    """Consulta PromQL instantanea. Devuelve [(etiquetas, valor)]."""
    params = {"query": expr}
    if momento is not None:
        params["time"] = momento
    r = httpx.get(f"{PROMETHEUS}/api/v1/query", params=params, timeout=15)
    r.raise_for_status()
    return [(s["metric"], float(s["value"][1])) for s in r.json()["data"]["result"]]


def consultar_rango(expr: str, inicio: float, fin: float, paso: int = 15) -> list:
    r = httpx.get(f"{PROMETHEUS}/api/v1/query_range",
                  params={"query": expr, "start": inicio, "end": fin, "step": paso}, timeout=30)
    r.raise_for_status()
    return r.json()["data"]["result"]


def alertas() -> list:
    r = httpx.get(f"{PROMETHEUS}/api/v1/alerts", timeout=15)
    r.raise_for_status()
    return r.json()["data"]["alerts"]


def valores_secretos() -> list:
    """Passwords y tokens de los .env (se comparan, nunca se imprimen)."""
    valores = []
    for ruta in (HITO10 / ".env", HITO13 / ".env"):
        if ruta.exists():
            for linea in ruta.read_text(encoding="utf-8").splitlines():
                if "=" in linea and not linea.startswith("#"):
                    clave, valor = linea.split("=", 1)
                    if any(k in clave for k in ("PASSWORD", "TOKEN")) and valor.strip():
                        valores.append(valor.strip())
    return valores


def controlar_secretos(carpeta: Path = None) -> str:
    """RNF6: busca los valores de los .env en la evidencia. Informa cantidad, no el valor."""
    carpeta = carpeta or EVIDENCIA
    secretos = valores_secretos()
    if not secretos:
        return "control de secretos: SIN EJECUTAR (no hay .env para comparar)"
    archivos = [p for p in carpeta.rglob("*") if p.suffix in (".txt", ".json", ".md") and p.is_file()]
    con_secretos = [p.name for p in archivos if any(s in p.read_text(encoding="utf-8", errors="ignore") for s in secretos)]
    if con_secretos:
        return f"control de secretos: FALLA en {con_secretos} (borrar esos archivos antes de commitear)"
    return f"control de secretos: OK ({len(secretos)} valores buscados en {len(archivos)} archivos, 0 coincidencias)"


def esperar(condicion, maximo_s: float, cada_s: float = 5):
    """Devuelve los segundos que tardo en cumplirse la condicion, o None si no se cumplio."""
    inicio = time.time()
    while time.time() - inicio < maximo_s:
        try:
            if condicion():
                return round(time.time() - inicio, 1)
        except httpx.HTTPError:
            pass
        time.sleep(cada_s)
    return None
