# -*- coding: utf-8 -*-
"""Hito 12 - funciones que comparten los scripts: rutas, configuracion,
version del codigo y datos del entorno donde se corrio la prueba."""

import math
import os
import platform
import subprocess
import sys
from datetime import datetime
from importlib import metadata
from pathlib import Path

# En Git Bash (Windows) la salida no es una consola: sin esto Python la guarda
# en un buffer (no se ve el avance) y puede fallar al imprimir acentos.
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

HITO12 = Path(__file__).resolve().parent.parent
HITO10 = HITO12.parent / "fixture2030-hito-10-api-integrada"
EVIDENCIA = HITO12 / "docs" / "evidencia"
TRABAJO = HITO12 / "trabajo"  # archivos intermedios (ids escritos, log de la API); no se versiona

# Datos del partido de laboratorio (mismos codigos que el resto del Fixture)
INICIO_PARTIDO = datetime.fromisoformat("2030-06-18T18:00:00+00:00")  # F2030-006, ARG vs ESP
DURACION_S = 6300            # 105 minutos, como en el Hito 8
EQUIPOS = ("ARG", "ESP")
MOMENTO_ACTUAL_S = 3600      # la prueba simula el minuto 60 del partido (19:00)


def bloque(segundo: int) -> str:
    """Bloque de 5 minutos del Hito 6 (AAAAMMDDHHmm) para un segundo del partido."""
    inicio = INICIO_PARTIDO.timestamp() + (segundo // 300) * 300
    return datetime.fromtimestamp(inicio, INICIO_PARTIDO.tzinfo).strftime("%Y%m%d%H%M")


def leer_env(ruta: Path) -> dict:
    datos = {}
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                clave, valor = linea.split("=", 1)
                datos[clave.strip()] = valor.strip()
    return datos


def configuracion() -> dict:
    """Parametros del escenario: el ejemplo versionado y, encima, config/local.env si existe."""
    conf = leer_env(HITO12 / "config" / "configuracion-ejemplo.env")
    conf.update(leer_env(HITO12 / "config" / "local.env"))
    return conf


def env_hito10() -> dict:
    """El .env del Hito 10 (hosts y token). Nunca se escribe en la evidencia."""
    ruta = HITO10 / ".env"
    if not ruta.exists():
        sys.exit("ERROR: falta fixture2030-hito-10-api-integrada/.env (ver el README del Hito 10).")
    datos = leer_env(ruta)
    if not datos.get("INFLUX_TOKEN"):
        sys.exit("ERROR: INFLUX_TOKEN vacio en el .env del Hito 10: correr antes scripts/sembrar_datos.sh del Hito 10.")
    return datos


def _git(*args) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=HITO12, capture_output=True, text=True, timeout=10)
        return r.stdout.rstrip()  # rstrip: en "git status --porcelain" el espacio inicial es parte del formato
    except (OSError, subprocess.SubprocessError):
        return ""


def version_codigo() -> dict:
    """Commit exacto y archivos de la API o del Hito 12 que no estaban commiteados."""
    cambios = _git("status", "--porcelain", "--", "../fixture2030-hito-10-api-integrada/app", "scripts", "config")
    return {
        "commit": _git("rev-parse", "--short", "HEAD").strip() or "desconocido",
        "rama": _git("rev-parse", "--abbrev-ref", "HEAD").strip(),
        "sin_commitear": [l[3:] for l in cambios.splitlines()],
    }


def _imagen(contenedor: str) -> str:
    try:
        r = subprocess.run(
            ["docker", "inspect", contenedor, "--format",
             "{{.Config.Image}} {{range .Config.Env}}{{println .}}{{end}}"],
            capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return "no se pudo consultar"
    lineas = r.stdout.split()
    if not lineas:
        return "no encontrado"
    versiones = [l for l in lineas[1:] if "_VERSION=" in l and not l.startswith(("PYTHON", "GOSU", "JAVA"))]
    return " ".join([lineas[0]] + versiones)


def entorno() -> dict:
    try:
        import psutil
        ram = f"{psutil.virtual_memory().total / 2**30:.1f} GB"
    except ImportError:
        ram = "no medido (falta psutil)"
    libs = {}
    for paquete in ("fastapi", "uvicorn", "httpx", "cassandra-driver", "psutil"):
        try:
            libs[paquete] = metadata.version(paquete)
        except metadata.PackageNotFoundError:
            libs[paquete] = "no instalado"
    return {
        "sistema": f"{platform.system()} {platform.release()}",
        "cpu_logicas": os.cpu_count(),
        "ram_total": ram,
        "python": platform.python_version(),
        "librerias": libs,
        "imagenes": {c: _imagen(c) for c in ("h10-cassandra", "h10-influxdb")},
    }


def ahora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def percentil(valores_ordenados: list, p: float) -> float:
    """Percentil por rango mas cercano (sin interpolar) sobre una lista ya ordenada."""
    if not valores_ordenados:
        return 0.0
    indice = max(0, min(len(valores_ordenados) - 1, math.ceil(p / 100 * len(valores_ordenados)) - 1))
    return valores_ordenados[indice]
