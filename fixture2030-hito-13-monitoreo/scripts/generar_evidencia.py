# -*- coding: utf-8 -*-
"""Hito 13 - Genera toda la evidencia de una vez, con la plataforma ya levantada.

    python scripts/generar_evidencia.py

Targets, captura en estado normal, carga transversal, falla controlada de Redis y capturas
de cada momento. Tarda unos 8 minutos. Termina con codigo 1 si falta algo importante.
"""

import json
import subprocess
import sys
import time

import httpx

from capturar import capturar
from comun import EVIDENCIA, HITO13, PROMETHEUS, alertas, consultar, controlar_secretos, esperar


def correr(*args):
    return subprocess.Popen([sys.executable, *args], cwd=str(HITO13))


def targets_arriba() -> bool:
    objetivos = httpx.get(f"{PROMETHEUS}/api/v1/targets", timeout=10).json()["data"]["activeTargets"]
    return len(objetivos) >= 5 and all(t["health"] == "up" for t in objetivos)


def api_arriba() -> bool:
    return any(v == 1 for _, v in consultar('up{job="fixture-api"}'))


def main() -> int:
    print("\n== Esperando que Prometheus vea los 5 targets (hasta 2 min)")
    if esperar(targets_arriba, 120, 5) is None:
        print("ATENCION: hay targets DOWN. Si es fixture-api, revisar el firewall de Windows (README, 'Target DOWN').")
    if correr("scripts/verificar_targets.py").wait() != 0:
        return 1
    print("Dejando 60 s para que Prometheus junte datos del estado normal...")
    time.sleep(60)
    if not api_arriba():
        print("ATENCION: la API no responde a Prometheus. No se sigue: la evidencia no serviria.")
        return 1
    capturas = [capturar("01_estado_normal"), capturar("06_targets_prometheus", f"{PROMETHEUS}/targets")]

    print("\n== Carga transversal (3 min)")
    carga = correr("scripts/generar_carga.py")
    time.sleep(120)
    capturas.append(capturar("02_durante_carga"))
    if carga.wait() != 0:
        print("ATENCION: la carga termino con error.")
        return 1
    if esperar(api_arriba, 45, 5) is None:
        print("ATENCION: la API dejo de responder durante la carga. No se sigue: la evidencia no serviria.")
        return 1

    print("\n== Falla controlada de Redis (~3 min)")
    falla = correr("scripts/ejecutar_prueba_controlada.py")

    def alerta_activa():
        return any(a["labels"]["alertname"] == "BaseDeDatosCaida" and a["labels"].get("database") == "redis"
                   and a["state"] == "firing" for a in alertas())

    if esperar(alerta_activa, 240, 5) is not None:
        capturas.append(capturar("03_falla_redis"))
        capturas.append(capturar("05_alertas_prometheus", f"{PROMETHEUS}/alerts"))
    else:
        print("ATENCION: no se vio la alerta en firing a tiempo para la captura.")
        capturas.append(False)
    if falla.wait() != 0:
        print("ATENCION: la prueba de falla termino con error.")
        return 1

    resultado = json.loads((EVIDENCIA / "prueba_de_falla.json").read_text(encoding="utf-8"))
    faltan = [k for k in ("deteccion_s", "alerta_firing_s", "ruta_200_s", "database_up_1_s") if resultado.get(k) is None]
    if faltan:
        print(f"ATENCION: la prueba de falla no completo: {faltan}. La evidencia no sirve.")
        return 1
    capturas.append(capturar("04_recuperacion", desde=int(resultado["inicio"] * 1000), hasta=int(resultado["fin"] * 1000)))

    arriba = {b["database"]: v for b, v in consultar("database_up")}
    print("\n== Resumen")
    print(f"Bases arriba: {sorted(k for k, v in arriba.items() if v == 1)}")
    print(f"Bases caidas: {sorted(k for k, v in arriba.items() if v != 1) or 'ninguna'}")
    print(f"Capturas logradas: {sum(1 for c in capturas if c)} de 6")
    control = controlar_secretos()
    print(control)
    # Sin las seis bases arriba, o sin las seis capturas, la evidencia no esta completa.
    completa = len(arriba) == 6 and all(v == 1 for v in arriba.values()) and sum(1 for c in capturas if c) == 6
    return 0 if completa and "OK" in control else 1


if __name__ == "__main__":
    sys.exit(main())
