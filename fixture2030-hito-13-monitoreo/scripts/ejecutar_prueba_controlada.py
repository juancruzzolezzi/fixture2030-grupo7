# -*- coding: utf-8 -*-
"""Hito 13 - Falla controlada de una base, observada en Prometheus (RF10).

    python scripts/ejecutar_prueba_controlada.py                     # detiene Redis
    python scripts/ejecutar_prueba_controlada.py --servicio influxdb --accion pausar

Con una carga baja de fondo: mide el estado antes, detiene la base con docker compose
(stop o pause, nunca borra volumenes), espera a que Prometheus lo detecte y la alerta
se dispare, comprueba que otro modulo sigue respondiendo, recupera la base y espera a
que todo vuelva. La salida queda en evidencia/prueba_de_falla.txt (y .json).
Aunque algo falle en el medio, la base siempre se vuelve a levantar.
"""

import argparse
import json
import subprocess
import sys
import threading
import time
from datetime import datetime

import httpx

from comun import (API, EVIDENCIA, GRAFANA, HITO10, alertas, consultar, consultar_rango, controlar_secretos,
                   encabezado, esperar)
from generar_carga import Carga, guardar, sembrar_sesion

# Rutas del Hito 11 para cada base
RUTAS = {
    "redis": "/sesiones/user-00001",
    "mongodb": "/equipos/ARG",
    "neo4j": "/partidos/F2030-006",
    "cassandra": "/partidos/F2030-006/comentarios?bloque_horario=203006181800",
    "influxdb": "/partidos/F2030-006/estadisticas?equipo_id=ARG&desde=2030-06-18T18:00:00Z&hasta=2030-06-18T18:05:00Z",
    "iris": "/partidos/F2030-006/entidad-compleja",
}
SALIDA = []


def anotar(texto=""):
    SALIDA.append(texto)
    print(texto)


def compose(*args):
    r = subprocess.run(["docker", "compose", *args], cwd=HITO10, capture_output=True, text=True)
    return r.returncode == 0


def pedir(ruta):
    inicio = time.perf_counter()
    try:
        r = httpx.get(API + ruta, timeout=20)
        tipo = r.json().get("error", {}).get("tipo", "") if r.status_code >= 400 else ""
        return f"HTTP {r.status_code} en {(time.perf_counter() - inicio) * 1000:.0f} ms {tipo}".rstrip()
    except httpx.HTTPError as exc:
        return type(exc).__name__


def estado_prometheus(servicio):
    arriba = consultar(f'database_up{{database="{servicio}"}}')
    anotar(f"  database_up{{database=\"{servicio}\"}} = {arriba[0][1] if arriba else 'sin datos'}")
    if servicio in ("redis", "mongodb"):
        directa = consultar(f"{servicio}_up")
        anotar(f"  {servicio}_up (exporter) = {directa[0][1] if directa else 'sin datos'}")
    anotar(f"  up{{job=\"fixture-api\"}} = {consultar('up{job=' + chr(34) + 'fixture-api' + chr(34) + '}')[0][1]}")
    activas = [f"{a['labels']['alertname']}({a['labels'].get('database', a['labels'].get('job', ''))})={a['state']}" for a in alertas()]
    anotar(f"  alertas: {', '.join(activas) if activas else 'ninguna'}")


def alerta_en(servicio, estado):
    return any(a["labels"]["alertname"] == "BaseDeDatosCaida" and a["labels"].get("database") == servicio
               and a["state"] == estado for a in alertas())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--servicio", choices=RUTAS, default="redis")
    p.add_argument("--accion", choices=("detener", "pausar"), default="detener")
    p.add_argument("--espera-inicial", type=int, default=60, help="segundos de estado normal antes de la falla")
    p.add_argument("--usuarios", type=int, default=10, help="usuarios de la carga de fondo (0 = sin carga)")
    a = p.parse_args()
    s = a.servicio
    cambio, vuelta = ("pause", "unpause") if a.accion == "pausar" else ("stop", "start")
    otro = "/partidos/F2030-006" if s == "mongodb" else "/equipos/ARG"

    if not consultar('up{job="fixture-api"}'):
        sys.exit("ERROR: Prometheus todavia no tiene datos de la API. Correr antes verificar_targets.py")

    for linea in encabezado(f"Hito 13 - Prueba de falla controlada: {s} ({a.accion})"):
        anotar(linea)
    carga, hilo = None, None
    if a.usuarios:
        sembrar_sesion()
        carga = Carga(argparse.Namespace(usuarios=a.usuarios, ops=1, duracion=3600, rampa=5, corte=0), silenciosa=True)
        hilo = threading.Thread(target=carga.correr, daemon=True)
        hilo.start()
        anotar(f"Carga de fondo: {a.usuarios} usuarios x 1 op/s, salida en resultados_sin_secretos/carga_durante_falla.txt")

    t_inicio = time.time()
    resultado = {"servicio": s, "accion": a.accion, "inicio": t_inicio}
    detenido = False
    try:
        anotar(f"\n== 1. Estado normal ({a.espera_inicial} s de linea base)")
        time.sleep(a.espera_inicial)
        anotar(f"  GET {RUTAS[s]}: {pedir(RUTAS[s])}")
        estado_prometheus(s)

        anotar(f"\n== 2. Falla aplicada: docker compose {cambio} {s} (sin borrar volumenes)")
        t_falla = time.time()
        if not compose(cambio, s):
            raise RuntimeError(f"docker compose {cambio} {s} fallo")
        detenido = True
        resultado["t_falla"] = t_falla
        anotar(f"  aplicada a las {datetime.fromtimestamp(t_falla).strftime('%H:%M:%S')}")

        anotar("\n== 3. Durante la falla")
        detectado = esperar(lambda: any(v == 0 for _, v in consultar(f'database_up{{database="{s}"}}')), 90, 3)
        resultado["deteccion_s"] = detectado
        anotar(f"  Prometheus vio database_up=0 a los {detectado} s" if detectado is not None
               else "  ATENCION: Prometheus no vio database_up=0 en 90 s")
        anotar(f"  GET {RUTAS[s]}: {pedir(RUTAS[s])}")
        anotar(f"  otro modulo, GET {otro}: {pedir(otro)}")
        pendiente = esperar(lambda: alerta_en(s, "firing"), 150, 5)
        resultado["alerta_firing_s"] = None if pendiente is None else round(time.time() - t_falla, 1)
        anotar(f"  alerta BaseDeDatosCaida en firing a los {resultado['alerta_firing_s']} s de la falla (for: 1m)"
               if pendiente is not None else "  ATENCION: la alerta no llego a firing en 150 s")
        estado_prometheus(s)
    finally:
        if detenido:
            anotar(f"\n== 4. Recuperacion: docker compose {vuelta} {s}")
            t_vuelta = time.time()
            compose(vuelta, s)
            resultado["t_recuperacion"] = t_vuelta

    r200 = esperar(lambda: httpx.get(API + RUTAS[s], timeout=10).status_code == 200, 120, 2)
    resultado["ruta_200_s"] = r200
    anotar(f"  la ruta volvio a 200 a los {r200} s" if r200 is not None else "  ATENCION: la ruta no volvio a 200 en 120 s")
    visto = esperar(lambda: any(v == 1 for _, v in consultar(f'database_up{{database="{s}"}}')), 90, 3)
    resultado["database_up_1_s"] = visto
    anotar(f"  Prometheus vio database_up=1 a los {visto} s de la ruta" if visto is not None else "  ATENCION: database_up no volvio a 1 en 90 s")
    apagada = esperar(lambda: not alerta_en(s, "firing"), 60, 5)
    anotar(f"  alerta fuera de firing a los {apagada} s" if apagada is not None else "  ATENCION: la alerta sigue en firing")

    anotar("\n== 5. Despues de recuperar")
    time.sleep(20)
    anotar(f"  GET {RUTAS[s]}: {pedir(RUTAS[s])}")
    estado_prometheus(s)
    t_fin = time.time()
    if carga:
        carga.parar.set()
        hilo.join(timeout=15)
        guardar(carga, t_inicio, t_fin, False, "carga_durante_falla")

    anotar("\n== 6. Serie observada en Prometheus (cada 15 s)")
    arriba = consultar_rango(f'database_up{{database="{s}"}}', t_inicio, t_fin)
    errores = consultar_rango('sum(rate(api_http_requests_total{clase="5xx"}[1m]))', t_inicio, t_fin)
    por_tiempo = {}
    for serie in arriba:
        for ts, v in serie["values"]:
            por_tiempo.setdefault(ts, {})["up"] = v
    for serie in errores:
        for ts, v in serie["values"]:
            por_tiempo.setdefault(ts, {})["err"] = v
    anotar(f"  {'hora':10}{'database_up':>13}{'5xx/s':>9}")
    for ts in sorted(por_tiempo):
        v = por_tiempo[ts]
        anotar(f"  {datetime.fromtimestamp(ts).strftime('%H:%M:%S'):10}{v.get('up', '-'):>13}{float(v.get('err', 0)):>9.2f}")
    resultado["fin"] = t_fin

    anotar(f"\nPara la captura en Grafana: {GRAFANA}/d/fixture2030?from={int(t_inicio * 1000)}&to={int(t_fin * 1000)}")
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    (EVIDENCIA / "prueba_de_falla.txt").write_text("\n".join(SALIDA) + "\n", encoding="utf-8")
    (EVIDENCIA / "prueba_de_falla.json").write_text(json.dumps(resultado, indent=2), encoding="utf-8")
    print(controlar_secretos())


if __name__ == "__main__":
    main()
