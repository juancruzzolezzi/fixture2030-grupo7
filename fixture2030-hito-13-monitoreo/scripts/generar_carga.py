# -*- coding: utf-8 -*-
"""Hito 13 - Carga transversal de laboratorio contra la API del puerto 8000.

    python scripts/generar_carga.py                         # 30 usuarios, 2 ops/s, 180 s
    python scripts/generar_carga.py --usuarios 10 --duracion 60

El Hito 12 ya cargo el flujo del partido en vivo (Cassandra + InfluxDB). Esta carga toca
las seis bases para ver en Grafana como se comporta cada una, con la misma cantidad de
usuarios y de operaciones por segundo que el Hito 12, y compara lo que mide el generador
con lo que queda en Prometheus.

Los comentarios van al bloque 203006182355, fuera del partido simulado, con usuarios
carga-h13-NN: no se mezclan con los datos sembrados y limpiar_entorno.sh los puede borrar.
La salida queda en evidencia/resultados_sin_secretos/carga.txt (o --nombre).
"""

import argparse
import json
import random
import subprocess
import threading
import time
import uuid

import httpx

from comun import API, EVIDENCIA, consultar, controlar_secretos, encabezado

PARTIDO = "F2030-006"
BLOQUE_LECTURA = "203006181800"
BLOQUE_CARGA = "203006182355"
VENTANA = {"equipo_id": "ARG", "desde": "2030-06-18T18:00:00Z", "hasta": "2030-06-18T18:05:00Z", "limite": 300}


def publicar(cliente, vu, n, run_id):
    return cliente.post(
        f"/partidos/{PARTIDO}/comentarios", params={"bloque_horario": BLOQUE_CARGA},
        json={"usuario_id": f"carga-h13-{vu:02d}", "usuario_nombre": f"carga {vu}",
              "contenido": f"[{run_id}] comentario de carga {n}", "clave_idempotencia": f"{run_id}-{vu:02d}-{n:05d}"})


# nombre, base, peso (%), funcion. La pantalla del partido en vivo pesa mas, como en el Hito 12.
OPERACIONES = (
    ("leer_comentarios", "cassandra", 25, lambda c, *_: c.get(f"/partidos/{PARTIDO}/comentarios", params={"bloque_horario": BLOQUE_LECTURA, "limite": 20})),
    ("publicar_comentario", "cassandra", 10, publicar),
    ("leer_estadisticas", "influxdb", 15, lambda c, *_: c.get(f"/partidos/{PARTIDO}/estadisticas", params=VENTANA)),
    ("leer_sesion", "redis", 15, lambda c, *_: c.get("/sesiones/user-00001")),
    ("leer_equipo", "mongodb", 10, lambda c, *_: c.get("/equipos/ARG")),
    ("leer_plantel", "mongodb", 5, lambda c, *_: c.get("/equipos/ARG/jugadores", params={"tamanio_pagina": 20})),
    ("leer_partido", "neo4j", 10, lambda c, *_: c.get(f"/partidos/{PARTIDO}")),
    ("leer_eventos", "neo4j", 5, lambda c, *_: c.get(f"/partidos/{PARTIDO}/eventos")),
    ("leer_entidad_compleja", "iris", 5, lambda c, *_: c.get(f"/partidos/{PARTIDO}/entidad-compleja")),
)


def percentil(ordenados, p):
    return ordenados[min(len(ordenados) - 1, int(len(ordenados) * p / 100))] if ordenados else 0.0


class Carga:
    def __init__(self, a, silenciosa=False):
        self.a, self.run_id, self.silenciosa = a, f"h13-{uuid.uuid4().hex[:6]}", silenciosa
        self.ops, self.lock, self.parar = [], threading.Lock(), threading.Event()

    def usuario(self, vu, t0):
        rng = random.Random(f"h13-vu-{vu}")
        if self.parar.wait(self.a.rampa * vu / max(1, self.a.usuarios - 1)):
            return
        intervalo = 1 / self.a.ops
        with httpx.Client(base_url=API, timeout=10) as cliente:
            proximo, n = time.monotonic(), 0
            while not self.parar.is_set() and time.monotonic() - t0 < self.a.duracion:
                nombre, _, _, funcion = rng.choices(OPERACIONES, weights=[o[2] for o in OPERACIONES])[0]
                inicio = time.perf_counter()
                try:
                    status = str(funcion(cliente, vu, n, self.run_id).status_code)
                except httpx.TimeoutException:
                    status = "timeout"
                except httpx.HTTPError:
                    status = "conexion"
                with self.lock:
                    self.ops.append((time.monotonic() - t0, nombre, status, (time.perf_counter() - inicio) * 1000))
                n += 1
                proximo += intervalo
                espera = proximo - time.monotonic()
                if espera > 0:
                    self.parar.wait(espera)
                else:
                    proximo = time.monotonic()

    def correr(self):
        t0 = time.monotonic()
        hilos = [threading.Thread(target=self.usuario, args=(i, t0), daemon=True) for i in range(self.a.usuarios)]
        for h in hilos:
            h.start()
        try:
            while any(h.is_alive() for h in hilos):
                time.sleep(1)
                t = time.monotonic() - t0
                with self.lock:
                    recientes = [o for o in self.ops if o[0] >= t - 5]
                malas = sum(1 for o in recientes if not o[2].startswith("2"))
                if self.a.corte and len(recientes) >= 20 and 100 * malas / len(recientes) > self.a.corte:
                    print(f"Corte seguro: {malas} de {len(recientes)} operaciones fallaron en 5 s (limite {self.a.corte} %)")
                    self.parar.set()
                if int(t) % 15 == 0 and not self.silenciosa:
                    print(f"  t={int(t):3d}/{self.a.duracion} s  ops={len(self.ops)}  no exitosas en 5 s={malas}")
                    time.sleep(1)
        except KeyboardInterrupt:
            print("Cortada a mano; se guarda lo medido.")
            self.parar.set()
        for h in hilos:
            h.join(timeout=12)


def resumen(ops):
    filas = [f"{'operacion':24}{'base':11}{'ops':>6}{'exitosas':>9}{'ops/s':>7}{'p50 ms':>8}{'p95 ms':>8}{'max ms':>9}  status"]
    duracion = max((o[0] for o in ops), default=1) or 1
    for nombre, base, _, _ in OPERACIONES:
        sel = [o for o in ops if o[1] == nombre]
        ok = sorted(o[3] for o in sel if o[2].startswith("2"))
        estados = {}
        for o in sel:
            estados[o[2]] = estados.get(o[2], 0) + 1
        filas.append(f"{nombre:24}{base:11}{len(sel):>6}{len(ok):>9}{len(sel) / duracion:>7.1f}{percentil(ok, 50):>8.1f}"
                     f"{percentil(ok, 95):>8.1f}{(ok[-1] if ok else 0):>9.1f}  {dict(sorted(estados.items()))}")
    ok = sorted(o[3] for o in ops if o[2].startswith("2"))
    filas.append(f"{'total':24}{'':11}{len(ops):>6}{len(ok):>9}{len(ops) / duracion:>7.1f}{percentil(ok, 50):>8.1f}"
                 f"{percentil(ok, 95):>8.1f}{(ok[-1] if ok else 0):>9.1f}")
    return filas


def promql(duracion, fin):
    """Lo mismo, leido de Prometheus con la ventana de la carga. Unidades: s y ops/s."""
    ventana = f"{duracion}s"
    consultas = (
        ("p95 de la API por ruta (s)", f"histogram_quantile(0.95, sum by (le, ruta) (rate(api_latency_seconds_bucket[{ventana}])))", "ruta"),
        ("p95 por base, medido en el adaptador (s)", f"histogram_quantile(0.95, sum by (le, database) (rate(database_query_duration_seconds_bucket[{ventana}])))", "database"),
        ("operaciones por segundo por base", f"sum by (database) (rate(database_operations_total[{ventana}]))", "database"),
        ("fallas por segundo por base", f"sum by (database) (rate(database_errors_total[{ventana}]))", "database"),
        ("requests por segundo por clase de status", f"sum by (clase) (rate(api_http_requests_total[{ventana}]))", "clase"),
    )
    filas = []
    for titulo, expr, etiqueta in consultas:
        filas += ["", f"{titulo}", f"  PromQL: {expr}"]
        resultado = consultar(expr, fin)
        filas += [f"  {r.get(etiqueta, '-'):38}{'sin datos' if v != v else f'{v:.4f}'}"
                  for r, v in sorted(resultado, key=lambda x: x[0].get(etiqueta, ""))] or ["  sin series en esta ventana"]
    return filas


def sembrar_sesion():
    """La sesion de prueba vence a los 30 min (TTL del Hito 7): se vuelve a crear, como
    scripts/redis/sembrar.sh del Hito 10. Se llama a docker directo: en Windows, "bash" desde
    Python puede abrir el de WSL en lugar del de Git Bash."""
    clave = "fixture2030:sesion:user-00001"
    comandos = (["HSET", clave, "rol", "fan", "estado", "activa", "ultimo_acceso", "2030-06-18T18:00:00Z",
                 "paginas_vistas", "3", "token", "tok-demo-no-real"], ["EXPIRE", clave, "1800"])
    for comando in comandos:
        r = subprocess.run(["docker", "exec", "h10-redis", "redis-cli", *comando], capture_output=True, text=True)
        if r.returncode != 0:
            print("AVISO: no se pudo sembrar la sesion de Redis; /sesiones puede dar 404.")
            return


def guardar(carga, inicio, fin, con_prometheus, nombre):
    a = carga.a
    lineas = encabezado(f"Hito 13 - Carga transversal | corrida {carga.run_id}")
    lineas += [f"Escenario: {a.usuarios} usuarios x {a.ops:g} ops/s = {a.usuarios * a.ops:g} ops/s objetivo; {fin - inicio:.0f} s, rampa {a.rampa} s; "
               f"pesos {', '.join(f'{o[0]} {o[2]}%' for o in OPERACIONES)}",
               f"Ventana (unix): {inicio:.0f} a {fin:.0f}", "",
               "== Medido por el generador (latencia solo de respuestas 2xx)"] + resumen(carga.ops)
    if con_prometheus:
        print("Esperando 20 s para que Prometheus lea las ultimas metricas...")
        time.sleep(20)
        duracion = max(30, int(fin - inicio))
        lineas += ["", f"== Leido de Prometheus al terminar la carga (ventana de {duracion} s)"]
        try:
            lineas += promql(duracion, fin)
        except httpx.HTTPError as exc:
            lineas.append(f"Prometheus no respondio: {type(exc).__name__}")
    destino = EVIDENCIA / "resultados_sin_secretos"
    destino.mkdir(parents=True, exist_ok=True)
    texto = "\n".join(lineas) + "\n"
    (destino / f"{nombre}.txt").write_text(texto, encoding="utf-8")
    (destino / f"{nombre}.json").write_text(json.dumps(
        {"run_id": carga.run_id, "inicio": inicio, "fin": fin, "usuarios": a.usuarios, "ops_por_usuario": a.ops,
         "operaciones": len(carga.ops)}, indent=2), encoding="utf-8")
    return texto


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--usuarios", type=int, default=30)
    p.add_argument("--ops", type=float, default=2, help="operaciones por segundo por usuario")
    p.add_argument("--duracion", type=int, default=180, help="segundos totales, incluida la rampa")
    p.add_argument("--rampa", type=int, default=20)
    p.add_argument("--corte", type=float, default=20, help="se detiene si falla mas de este %% en 5 s (0 = sin corte)")
    p.add_argument("--nombre", default="carga", help="nombre del archivo de resultados")
    p.add_argument("--sin-prometheus", action="store_true", help="no consulta Prometheus al terminar")
    a = p.parse_args()

    sembrar_sesion()
    carga = Carga(a)
    print(f"Carga {carga.run_id}: {a.usuarios} usuarios x {a.ops:g} ops/s durante {a.duracion} s (rampa {a.rampa} s) contra {API}")
    inicio = time.time()
    carga.correr()
    print(guardar(carga, inicio, time.time(), not a.sin_prometheus, a.nombre) + controlar_secretos())


if __name__ == "__main__":
    main()
