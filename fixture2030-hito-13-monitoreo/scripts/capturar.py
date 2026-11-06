# -*- coding: utf-8 -*-
"""Hito 13 - Saca una captura de Grafana o Prometheus (evidencia/dashboards/).

    python scripts/capturar.py 01_estado_normal                       # dashboard, ultimos 15 min
    python scripts/capturar.py 04_recuperacion --desde MS --hasta MS  # dashboard, rango fijo
    python scripts/capturar.py 06_targets --url http://127.0.0.1:9090/targets

Usa Microsoft Edge (viene con Windows) o el Chromium de Playwright. Entra a Grafana con el
usuario del laboratorio; la password viaja en el pedido y no se ve en la captura. Si no llega
al dashboard, no guarda nada y lo avisa.
"""

import argparse
import os
import sys

from comun import EVIDENCIA, GRAFANA, HITO13

ALTO_DASHBOARD = 2350  # entra el dashboard completo, sin scroll
PANEL_DE_CONTROL = "Estado de salud por base"  # un titulo del dashboard: confirma que no quedo en el login


def password_grafana() -> str:
    ruta = HITO13 / ".env"
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if linea.startswith("GRAFANA_PASSWORD="):
                return linea.split("=", 1)[1].strip()
    return ""


def capturar(nombre: str, url: str | None = None, desde: int | None = None, hasta: int | None = None) -> bool:
    from playwright.sync_api import Error, sync_playwright

    destino = EVIDENCIA / "dashboards"
    destino.mkdir(parents=True, exist_ok=True)
    es_grafana = url is None
    if es_grafana:
        rango = f"&from={desde}&to={hasta}" if desde and hasta else ""
        url = f"{GRAFANA}/d/fixture2030?kiosk{rango}"
    try:
        with sync_playwright() as p:
            try:
                navegador = p.chromium.launch(channel=os.environ.get("CANAL_NAVEGADOR", "msedge"))
            except Error:
                navegador = p.chromium.launch()
            contexto = navegador.new_context(viewport={"width": 1600, "height": ALTO_DASHBOARD if es_grafana else 1000})
            if es_grafana:
                # Inicia sesion antes de abrir el dashboard: Grafana no pide credenciales, redirige al login.
                sesion = contexto.request.post(f"{GRAFANA}/login", data={"user": "admin", "password": password_grafana()})
                if not sesion.ok:
                    print(f"AVISO: Grafana rechazo el inicio de sesion (HTTP {sesion.status}); no se saca {nombre}.")
                    navegador.close()
                    return False
            pagina = contexto.new_page()
            pagina.goto(url, wait_until="load", timeout=60000)
            if es_grafana:
                pagina.get_by_text(PANEL_DE_CONTROL).first.wait_for(timeout=45000)  # si no aparece, no es el dashboard
                pagina.wait_for_timeout(10000)
            else:
                pagina.wait_for_timeout(3000)
            pagina.screenshot(path=str(destino / f"{nombre}.png"))
            navegador.close()
        print(f"Captura guardada: dashboards/{nombre}.png")
        return True
    except Error as exc:
        print(f"AVISO: no se pudo sacar la captura {nombre}: {str(exc).splitlines()[0]}")
        return False


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("nombre")
    a.add_argument("--url")
    a.add_argument("--desde", type=int)
    a.add_argument("--hasta", type=int)
    v = a.parse_args()
    sys.exit(0 if capturar(v.nombre, v.url, v.desde, v.hasta) else 1)
