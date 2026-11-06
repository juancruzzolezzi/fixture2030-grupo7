# -*- coding: utf-8 -*-
"""Hito 13 - Vuelve a sacar las capturas de Grafana de la ultima corrida, sin repetirla.

    python scripts/recapturar.py

Prometheus conserva las metricas: con los rangos de carga.json y prueba_de_falla.json, el
dashboard muestra exactamente esos momentos. Primero confirma que Grafana tenga cargada la
version del dashboard de este repositorio; si no, no saca nada.
"""

import json
import sys
import time

import httpx

from capturar import capturar, password_grafana
from comun import EVIDENCIA, GRAFANA, HITO13


def dashboard_al_dia() -> bool:
    esperado = json.loads((HITO13 / "grafana" / "dashboards" / "fixture2030.json").read_text(encoding="utf-8"))
    titulos = {p["title"] for p in esperado["panels"]}
    try:
        r = httpx.get(f"{GRAFANA}/api/dashboards/uid/fixture2030", auth=("admin", password_grafana()), timeout=10)
        return r.status_code == 200 and titulos == {p["title"] for p in r.json()["dashboard"]["panels"]}
    except (httpx.HTTPError, ValueError, KeyError):
        return False


def main() -> int:
    print("Esperando que Grafana cargue el dashboard del repositorio (hasta 2 min)...")
    for _ in range(24):
        if dashboard_al_dia():
            break
        time.sleep(5)
    else:
        print("ATENCION: Grafana sigue con otra version del dashboard. No se sacan capturas.")
        return 1

    carga = json.loads((EVIDENCIA / "resultados_sin_secretos" / "carga.json").read_text(encoding="utf-8"))
    falla = json.loads((EVIDENCIA / "prueba_de_falla.json").read_text(encoding="utf-8"))
    ms = lambda t: int(t * 1000)
    desde = carga["inicio"] - 90
    rangos = {
        "01_estado_normal": (desde, carga["inicio"] - 5),
        "02_durante_carga": (desde, carga["inicio"] + 125),
        "03_falla_redis": (desde, falla["t_falla"] + falla["alerta_firing_s"]),  # Redis todavia detenido
        "04_recuperacion": (falla["inicio"], falla["fin"]),
    }
    resultados = [capturar(nombre, desde=ms(a), hasta=ms(b)) for nombre, (a, b) in rangos.items()]
    print(f"Capturas logradas: {sum(resultados)} de {len(resultados)}")
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
