# -*- coding: utf-8 -*-
"""Hito 13 - Verifica que cada target este UP y que las metricas clave existan.

    python scripts/verificar_targets.py

Guarda la salida en evidencia/prometheus_targets.txt (y .json). Termina con codigo
1 si algun target esta DOWN. Que hacer en ese caso: README, seccion "Target DOWN".
"""

import json
import sys

import httpx

from comun import API, EVIDENCIA, GRAFANA, PROMETHEUS, consultar, controlar_secretos, encabezado

METRICAS_CLAVE = {
    "API (aplicacion)": ["api_http_requests_total", "api_latency_seconds_bucket", "database_up",
                         "database_query_duration_seconds_bucket", "database_operations_total"],
    "Redis (exporter)": ["redis_up", "redis_memory_used_bytes", "redis_memory_max_bytes", "redis_commands_processed_total"],
    "MongoDB (exporter)": ["mongodb_up", "mongodb_ss_connections", "mongodb_ss_opcounters"],
    "Host Docker (exporter)": ["node_cpu_seconds_total", "node_memory_MemAvailable_bytes"],
}


def estado_http(url: str) -> str:
    try:
        return str(httpx.get(url, timeout=5).status_code)
    except httpx.HTTPError as exc:
        return type(exc).__name__


def main() -> int:
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    try:
        targets = httpx.get(f"{PROMETHEUS}/api/v1/targets", timeout=10).json()["data"]["activeTargets"]
    except httpx.HTTPError as exc:
        print(f"ERROR: Prometheus no responde en {PROMETHEUS} ({type(exc).__name__}). Correr scripts/iniciar_monitoreo.sh")
        return 1

    lineas = encabezado("Hito 13 - Targets de Prometheus")
    lineas += ["", f"{'job':18}{'capa':17}{'componente':15}{'estado':8}{'scrape ms':>10}  endpoint"]
    for t in sorted(targets, key=lambda x: x["labels"]["job"]):
        e = t["labels"]
        lineas.append(f"{e['job']:18}{e.get('capa', '-'):17}{e.get('componente', '-'):15}{t['health'].upper():8}"
                      f"{t['lastScrapeDuration'] * 1000:>10.1f}  {t['scrapeUrl']}")
        if t["lastError"]:
            lineas.append(f"    ultimo error: {t['lastError']}")

    lineas += ["", "Estado de cada base segun la API (database_up, 1 = responde):"]
    bases = consultar("database_up")
    lineas += [f"  {b['database']:12}{'UP' if v == 1 else 'DOWN'}" for b, v in sorted(bases, key=lambda x: x[0]["database"])]
    if not bases:
        lineas.append("  sin datos: la API todavia no fue leida por Prometheus")

    lineas += ["", "Metricas clave (series encontradas):"]
    for grupo, nombres in METRICAS_CLAVE.items():
        lineas.append(f"  {grupo}")
        lineas += [f"    {n:44}{len(consultar(n))}" for n in nombres]

    lineas += ["", f"API /salud/vivo: HTTP {estado_http(API + '/salud/vivo')} | Prometheus /-/healthy: "
               f"HTTP {estado_http(PROMETHEUS + '/-/healthy')} | Grafana /api/health: HTTP {estado_http(GRAFANA + '/api/health')}"]
    caidos = [t["labels"]["job"] for t in targets if t["health"] != "up"]
    lineas.append(f"Resultado: {len(targets) - len(caidos)} de {len(targets)} targets UP" + (f"; DOWN: {caidos}" if caidos else ""))

    texto = "\n".join(lineas) + "\n"
    (EVIDENCIA / "prometheus_targets.txt").write_text(texto, encoding="utf-8")
    (EVIDENCIA / "prometheus_targets.json").write_text(json.dumps(
        [{"job": t["labels"]["job"], "labels": t["labels"], "health": t["health"], "scrapeUrl": t["scrapeUrl"],
          "lastError": t["lastError"], "lastScrape": t["lastScrape"]} for t in targets], indent=2), encoding="utf-8")
    print(texto + controlar_secretos())
    return 1 if caidos else 0


if __name__ == "__main__":
    sys.exit(main())
