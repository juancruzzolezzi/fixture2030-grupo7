# -*- coding: utf-8 -*-
"""Hito 12 - Comparacion linea base vs optimizada.

Lee docs/evidencia/resultados_{linea_base,optimizada}.json e integridad_*.txt
y arma docs/evidencia/comparacion.md y grafico_p95.svg. Antes de comparar
revisa que las dos corridas tengan el mismo escenario y el mismo entorno.

  python scripts/comparar.py
"""

import json
import sys

from comun import EVIDENCIA, ahora

TIPOS = ("leer_comentarios", "publicar_comentario", "leer_estadisticas", "total")


def cargar(modo: str) -> dict:
    ruta = EVIDENCIA / f"resultados_{modo}.json"
    if not ruta.exists():
        sys.exit(f"ERROR: falta {ruta.name}: correr antes la corrida '{modo}'")
    return json.loads(ruta.read_text(encoding="utf-8"))


def variacion(antes: float, despues: float) -> str:
    if not antes:
        return "-"
    return f"{(despues - antes) / antes * 100:+.0f} %"


def promedio(muestras: list, clave: str) -> float | None:
    valores = [m[clave] for m in muestras if m["fase"] == "sostenimiento" and clave in m]
    return sum(valores) / len(valores) if valores else None


def grafico(base: dict, opt: dict) -> str:
    """Barras de p95 por operacion (SVG simple, se ve directo en GitHub)."""
    ancho, alto, margen = 640, 300, 50
    valores = [(t, base["metricas"]["sostenimiento"][t].get("p95", 0), opt["metricas"]["sostenimiento"][t].get("p95", 0))
               for t in TIPOS]
    tope = max(max(b, o) for _, b, o in valores) * 1.15 or 1
    grupo = (ancho - 2 * margen) / len(valores)
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" font-family="sans-serif" font-size="12">',
              f'<rect width="{ancho}" height="{alto}" fill="white"/>',
              f'<text x="{margen}" y="20" font-size="14">p95 de latencia en el sostenimiento (ms, menor es mejor)</text>',
              f'<line x1="{margen}" y1="{alto - margen}" x2="{ancho - margen}" y2="{alto - margen}" stroke="#333"/>']
    for i, (tipo, b, o) in enumerate(valores):
        x = margen + i * grupo + 10
        for j, (valor, color) in enumerate(((b, "#c0504d"), (o, "#4f81bd"))):
            h = valor / tope * (alto - 2 * margen - 20)
            xb = x + j * (grupo / 2 - 8)
            partes.append(f'<rect x="{xb:.0f}" y="{alto - margen - h:.0f}" width="{grupo / 2 - 14:.0f}" height="{h:.0f}" fill="{color}"/>')
            partes.append(f'<text x="{xb + 2:.0f}" y="{alto - margen - h - 4:.0f}">{valor:.0f}</text>')
        partes.append(f'<text x="{x:.0f}" y="{alto - margen + 16}">{tipo}</text>')
    partes += [f'<rect x="{ancho - 200}" y="32" width="12" height="12" fill="#c0504d"/>',
               f'<text x="{ancho - 182}" y="43">linea base ({base["run_id"]})</text>',
               f'<rect x="{ancho - 200}" y="50" width="12" height="12" fill="#4f81bd"/>',
               f'<text x="{ancho - 182}" y="61">optimizada ({opt["run_id"]})</text>', "</svg>"]
    return "\n".join(partes) + "\n"


def main() -> None:
    base, opt = cargar("linea_base"), cargar("optimizada")

    # Condiciones: tiene que cambiar solo INFLUX_REUSAR_CLIENTE
    controles = [
        ("mismo escenario (config)", base["configuracion"] == opt["configuracion"]),
        ("mismo commit", base["version"]["commit"] == opt["version"]["commit"]),
        ("mismo entorno (SO, CPU, RAM, versiones)", base["entorno"] == opt["entorno"]),
        ("las dos corridas completas", base["estado"] == opt["estado"] == "completa"),
    ]
    sb, so = base["metricas"]["sostenimiento"], opt["metricas"]["sostenimiento"]
    lineas = [
        "# Comparación: línea base vs optimizada",
        "",
        f"Generado por `scripts/comparar.py` el {ahora()}. Los números salen de `resultados_linea_base.json` "
        f"y `resultados_optimizada.json`; no se editan a mano.",
        "",
        "| | Línea base | Optimizada |",
        "|---|---|---|",
        f"| Corrida | {base['run_id']} ({base['fecha']}) | {opt['run_id']} ({opt['fecha']}) |",
        f"| Commit | {base['version']['commit']} | {opt['version']['commit']} |",
        f"| `INFLUX_REUSAR_CLIENTE` | 0 (cliente nuevo por consulta) | 1 (cliente compartido) |",
        f"| Estado | {base['estado']} | {opt['estado']} |",
        "",
        "Condiciones de la comparación:",
        "",
    ]
    lineas += [f"- {texto}: {'sí' if ok else '**NO** (ver diferencias en los .json)'}" for texto, ok in controles]
    lineas += [
        "",
        f"## Sostenimiento ({sb['duracion_s']} s con {base['configuracion']['USUARIOS_VIRTUALES']} usuarios virtuales, "
        f"{base['tasa_objetivo']:.0f} ops/s objetivo)",
        "",
        "Latencia en ms medida por el generador, solo respuestas correctas (status y contenido).",
        "",
        "| Operación | ops ok/s base → opt | errores base → opt | p50 base → opt | p95 base → opt | Δ p95 | p99 base → opt |",
        "|---|---|---|---|---|---|---|",
    ]
    for t in TIPOS:
        b, o = sb[t], so[t]
        lineas.append(f"| {t} | {b['ok_por_s']} → {o['ok_por_s']} | {b['errores']} → {o['errores']} | "
                      f"{b.get('p50', '-')} → {o.get('p50', '-')} | {b.get('p95', '-')} → {o.get('p95', '-')} | "
                      f"{variacion(b.get('p95', 0), o.get('p95', 0))} | {b.get('p99', '-')} → {o.get('p99', '-')} |")
    lineas += ["", "![p95 por operación](grafico_p95.svg)", "", "## Recursos (promedio en el sostenimiento)", "",
               "| Medida | Línea base | Optimizada | Δ |", "|---|---|---|---|"]
    for clave, nombre in (("api_cpu_pct", "CPU de la API (% de 1 núcleo)"), ("api_mem_mb", "Memoria de la API (MB)"),
                          ("generador_cpu_pct", "CPU del generador (%)"), ("cassandra_cpu_pct", "CPU h10-cassandra (%)"),
                          ("influxdb_cpu_pct", "CPU h10-influxdb (%)")):
        vb, vo = promedio(base["recursos"], clave), promedio(opt["recursos"], clave)
        if vb is None or vo is None:
            lineas.append(f"| {nombre} | no medido | no medido | - |")
        else:
            lineas.append(f"| {nombre} | {vb:.0f} | {vo:.0f} | {variacion(vb, vo)} |")
    lineas += ["", "## Integridad", ""]
    for modo in ("linea_base", "optimizada"):
        ruta = EVIDENCIA / f"integridad_{modo}.txt"
        if ruta.exists():
            estados = [l[1:9].strip() for l in ruta.read_text(encoding="utf-8").splitlines() if l.startswith("[")]
            resumen = ", ".join(f"{estados.count(e)} {e}" for e in ("OK", "FALLA", "HALLAZGO") if estados.count(e))
            lineas.append(f"- {modo}: {resumen} (detalle en `integridad_{modo}.txt`)")
        else:
            lineas.append(f"- {modo}: no se corrió `validar_integridad.py`")
    (EVIDENCIA / "comparacion.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    (EVIDENCIA / "grafico_p95.svg").write_text(grafico(base, opt), encoding="utf-8")
    print("\n".join(lineas))
    print("\n-> docs/evidencia/comparacion.md y grafico_p95.svg")


if __name__ == "__main__":
    main()
