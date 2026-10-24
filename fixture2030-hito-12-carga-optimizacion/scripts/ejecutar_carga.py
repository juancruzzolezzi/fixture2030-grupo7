# -*- coding: utf-8 -*-
"""Hito 12 - Prueba de carga del flujo "pantalla del partido en vivo".

Levanta una instancia propia de la API del Hito 10 (puerto PUERTO_API,
apuntando a los datos de laboratorio), genera la carga con usuarios virtuales
y guarda las metricas en docs/evidencia/resultados_<modo>.{txt,json}.

  python scripts/ejecutar_carga.py --modo linea_base   # API como en el Hito 10 (INFLUX_REUSAR_CLIENTE=0)
  python scripts/ejecutar_carga.py --modo optimizada   # API con el cliente de InfluxDB compartido (=1)

Las dos corridas usan el mismo escenario, los mismos datos y la misma
secuencia de operaciones por usuario virtual (semilla fija): lo unico que
cambia es esa variable.
"""

import argparse
import json
import os
import random
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime

import httpx

from comun import (EVIDENCIA, HITO10, MOMENTO_ACTUAL_S, TRABAJO, INICIO_PARTIDO, ahora, bloque, configuracion,
                   entorno, env_hito10, percentil, version_codigo)

try:
    import psutil
except ImportError:  # sin psutil la prueba corre igual, pero sin CPU/memoria de la API
    psutil = None

MODOS = {"linea_base": "0", "optimizada": "1"}  # valor de INFLUX_REUSAR_CLIENTE en cada corrida
TIPOS = ("leer_comentarios", "publicar_comentario", "leer_estadisticas")
FASES = ("calentamiento", "rampa", "sostenimiento")
PAUSA_RECURSOS_S = 5


# --- Preparacion: API propia para la prueba ------------------------------------

def puerto_ocupado(puerto: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def levantar_api(modo: str, conf: dict, log) -> subprocess.Popen:
    env = os.environ.copy()
    env.update(env_hito10())
    env.update(CASSANDRA_KEYSPACE=conf["KEYSPACE_PRUEBA"], INFLUX_DATABASE=conf["INFLUX_DB_PRUEBA"],
               INFLUX_REUSAR_CLIENTE=MODOS[modo])
    # Sin --reload y con un solo proceso: es la forma en que corre la API en el Hito 10, sin el vigilante de archivos.
    comando = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
               "--port", conf["PUERTO_API"], "--log-level", "warning", "--no-access-log"]
    proceso = subprocess.Popen(comando, cwd=HITO10, env=env, stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{conf['PUERTO_API']}/salud/vivo"
    for _ in range(60):
        if proceso.poll() is not None:
            sys.exit(f"ERROR: la API no arranco; ver {log.name}")
        try:
            if httpx.get(url, timeout=1).status_code == 200:
                return proceso
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    detener_api(proceso)
    sys.exit("ERROR: la API no respondio /salud/vivo en 30 s")


def detener_api(proceso: subprocess.Popen) -> None:
    # En Windows el python del venv es un lanzador que abre otro proceso: se cierran los dos.
    hijos = psutil.Process(proceso.pid).children(recursive=True) if psutil and proceso.poll() is None else []
    for p in hijos:
        p.terminate()
    proceso.terminate()
    try:
        proceso.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proceso.kill()


# --- Operaciones del flujo ----------------------------------------------------

class Escenario:
    def __init__(self, conf: dict, run_id: str):
        self.partido = conf["PARTIDO"]
        self.run_id = run_id
        self.bloque_actual = bloque(MOMENTO_ACTUAL_S)
        self.bloques_previos = [bloque(s) for s in range(0, MOMENTO_ACTUAL_S, 300)]
        fin = INICIO_PARTIDO.timestamp() + MOMENTO_ACTUAL_S
        self.hasta = datetime.fromtimestamp(fin, INICIO_PARTIDO.tzinfo).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.desde = datetime.fromtimestamp(fin - 300, INICIO_PARTIDO.tzinfo).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.lock = threading.Lock()
        self.aceptados, self.rechazados, self.desconocidos = [], [], []

    def leer_comentarios(self, cliente, rng, vu, n):
        # 80 % el bloque actual (todos miran lo ultimo), 20 % un bloque anterior del partido
        b = self.bloque_actual if rng.random() < 0.8 else rng.choice(self.bloques_previos)
        r = cliente.get(f"/partidos/{self.partido}/comentarios", params={"bloque_horario": b, "limite": 20})
        if r.status_code != 200:
            return f"http_{r.status_code}"
        items = r.json()["items"]
        # Todos los bloques tienen al menos 300 comentarios: tienen que volver 20, del bloque pedido
        return None if len(items) == 20 else "contenido_invalido"

    def publicar_comentario(self, cliente, rng, vu, n):
        clave = f"{self.run_id}-{vu:03d}-{n:05d}"
        cuerpo = {"usuario_id": f"carga-{vu:03d}", "usuario_nombre": f"usuario virtual {vu}",
                  "contenido": f"[{self.run_id}] comentario {n} del usuario virtual {vu}", "clave_idempotencia": clave}
        try:
            r = cliente.post(f"/partidos/{self.partido}/comentarios", params={"bloque_horario": self.bloque_actual},
                             json=cuerpo)
        except httpx.HTTPError:
            with self.lock:  # no se sabe si llego a escribirse: lo resuelve validar_integridad
                self.desconocidos.append({"clave": clave, "usuario_id": cuerpo["usuario_id"]})
            raise
        with self.lock:
            if r.status_code == 201 and r.json().get("comentario_id"):
                self.aceptados.append({"clave": clave, "id": r.json()["comentario_id"], "usuario_id": cuerpo["usuario_id"]})
                return None
            self.rechazados.append({"clave": clave, "status": r.status_code})
        return f"http_{r.status_code}" if r.status_code != 201 else "contenido_invalido"

    def leer_estadisticas(self, cliente, rng, vu, n):
        # Ultimos 5 minutos de un equipo: 1 punto por segundo -> tienen que volver 300, ordenados
        equipo = rng.choice(("ARG", "ESP"))
        r = cliente.get(f"/partidos/{self.partido}/estadisticas",
                        params={"equipo_id": equipo, "desde": self.desde, "hasta": self.hasta, "limite": 300})
        if r.status_code != 200:
            return f"http_{r.status_code}"
        tiempos = [i["time"] for i in r.json()["items"]]
        return None if len(tiempos) == 300 and tiempos == sorted(tiempos) else "contenido_invalido"


# --- Generador de carga -------------------------------------------------------

class Generador:
    def __init__(self, conf: dict, escenario: Escenario):
        self.conf, self.esc = conf, escenario
        self.vus = int(conf["USUARIOS_VIRTUALES"])
        self.vus_iniciales = max(1, self.vus // 6)
        self.intervalo = 1 / float(conf["OPS_POR_USUARIO_S"])
        self.cal, self.rampa, self.sost = (float(conf[k]) for k in ("CALENTAMIENTO_S", "RAMPA_S", "SOSTENIMIENTO_S"))
        self.mezcla = [float(conf[k]) for k in ("MEZCLA_LEER_COMENTARIOS", "MEZCLA_PUBLICAR_COMENTARIO", "MEZCLA_LEER_ESTADISTICAS")]
        self.url = f"http://127.0.0.1:{conf['PUERTO_API']}"
        self.timeout = float(conf["TIMEOUT_REQUEST_S"])
        self.ops = []          # (t_inicio, tipo, ms, error)
        self.lock = threading.Lock()
        self.parar = threading.Event()
        self.atrasadas = 0
        self.activos = 0
        self.t0 = 0.0

    def fase(self, t: float) -> str:
        return "calentamiento" if t < self.cal else ("rampa" if t < self.cal + self.rampa else "sostenimiento")

    def inicio_vu(self, i: int) -> float:
        if i < self.vus_iniciales:
            return 0.0
        return self.cal + (i - self.vus_iniciales + 1) / (self.vus - self.vus_iniciales) * self.rampa

    def usuario_virtual(self, i: int) -> None:
        rng = random.Random(f"vu-{i}")  # misma secuencia de operaciones en las dos corridas
        fin = self.t0 + self.cal + self.rampa + self.sost
        if self.parar.wait(max(0.0, self.t0 + self.inicio_vu(i) - time.monotonic())):
            return
        with self.lock:
            self.activos += 1
        with httpx.Client(base_url=self.url, timeout=self.timeout) as cliente:
            proximo, n = time.monotonic(), 0
            while not self.parar.is_set() and time.monotonic() < fin:
                tipo = rng.choices(TIPOS, weights=self.mezcla)[0]
                inicio = time.perf_counter()
                try:
                    error = getattr(self.esc, tipo)(cliente, rng, i, n)
                except httpx.TimeoutException:
                    error = "timeout"
                except httpx.HTTPError:
                    error = "conexion"
                except ValueError:  # cuerpo que no es JSON
                    error = "contenido_invalido"
                ms = (time.perf_counter() - inicio) * 1000
                with self.lock:
                    self.ops.append((inicio - self.t0_perf, tipo, ms, error))
                n += 1
                proximo += self.intervalo
                espera = proximo - time.monotonic()
                if espera > 0:
                    self.parar.wait(espera)
                else:  # la respuesta tardo mas que el intervalo: sale enseguida, sin acumular atraso
                    with self.lock:
                        self.atrasadas += 1
                    proximo = time.monotonic()
        with self.lock:
            self.activos -= 1

    def correr(self, muestreador) -> str:
        self.t0, self.t0_perf = time.monotonic(), time.perf_counter()
        hilos = [threading.Thread(target=self.usuario_virtual, args=(i,), daemon=True) for i in range(self.vus)]
        for h in hilos:
            h.start()
        muestreador.iniciar(self)
        motivo, duracion, proximo_aviso = "completa", self.cal + self.rampa + self.sost, 10
        try:
            while any(h.is_alive() for h in hilos):
                time.sleep(1)
                t = time.monotonic() - self.t0
                if proximo_aviso <= t <= duracion:
                    proximo_aviso += 10
                    with self.lock:
                        total, errores = len(self.ops), sum(1 for o in self.ops if o[3])
                    print(f"  t={int(t):3d}/{int(duracion)} s  usuarios activos={self.activos:2d}  ops={total}  errores={errores}")
                motivo = self.revisar_corte(t) or motivo
                if motivo != "completa":
                    self.parar.set()
        except KeyboardInterrupt:
            motivo = "interrumpida a mano (Ctrl+C)"
            self.parar.set()
        for h in hilos:
            h.join(timeout=self.timeout + 2)
        muestreador.detener()
        return motivo

    def revisar_corte(self, t: float) -> str | None:
        """Corte seguro: si en los ultimos 5 s fallo mas de CORTE_ERRORES_PCT de las operaciones."""
        if t < self.cal:
            return None
        with self.lock:
            recientes = [o for o in self.ops if o[0] >= t - 5]
        if len(recientes) >= 20:
            pct = 100 * sum(1 for o in recientes if o[3]) / len(recientes)
            if pct > float(self.conf["CORTE_ERRORES_PCT"]):
                return f"cortada: {pct:.0f} % de errores en 5 s (limite {self.conf['CORTE_ERRORES_PCT']} %)"
        return None


# --- Recursos: API, generador y contenedores ----------------------------------

class Muestreador:
    def __init__(self, api: subprocess.Popen):
        self.muestras = []
        self.parar = threading.Event()
        self.procesos_api = []
        if psutil:
            raiz = psutil.Process(api.pid)
            self.procesos_api = [raiz] + raiz.children(recursive=True)
            self.generador = psutil.Process()
            for p in self.procesos_api + [self.generador]:
                p.cpu_percent(None)  # la primera lectura solo fija el punto de partida

    def iniciar(self, gen: Generador) -> None:
        self.gen = gen
        self.hilo = threading.Thread(target=self.bucle, daemon=True)
        self.hilo.start()

    def detener(self) -> None:
        self.parar.set()
        self.hilo.join(timeout=15)

    def bucle(self) -> None:
        while not self.parar.wait(PAUSA_RECURSOS_S):
            t = time.monotonic() - self.gen.t0
            m = {"t": round(t, 1), "fase": self.gen.fase(t), "usuarios": self.gen.activos}
            if psutil:
                try:
                    m["api_cpu_pct"] = round(sum(p.cpu_percent(None) for p in self.procesos_api), 1)
                    m["api_mem_mb"] = round(sum(p.memory_info().rss for p in self.procesos_api) / 2**20, 1)
                    m["generador_cpu_pct"] = round(self.generador.cpu_percent(None), 1)
                except psutil.Error:
                    pass
            m.update(estadisticas_docker())
            self.muestras.append(m)


def _a_mb(texto: str) -> float:
    unidades = {"B": 1 / 2**20, "KiB": 1 / 1024, "kB": 1 / 1024, "MiB": 1, "MB": 1, "GiB": 1024, "GB": 1024}
    for u in sorted(unidades, key=len, reverse=True):
        if texto.endswith(u):
            return round(float(texto[: -len(u)]) * unidades[u], 1)
    return 0.0


def estadisticas_docker() -> dict:
    try:
        r = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}};{{.CPUPerc}};{{.MemUsage}}",
                            "h10-cassandra", "h10-influxdb"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return {}
    datos = {}
    for linea in r.stdout.splitlines():
        partes = linea.split(";")
        if len(partes) == 3:
            nombre = partes[0].replace("h10-", "")
            datos[f"{nombre}_cpu_pct"] = float(partes[1].rstrip("%") or 0)
            datos[f"{nombre}_mem_mb"] = _a_mb(partes[2].split("/")[0].strip())
    return datos


# --- Prueba de reintento (idempotencia) ---------------------------------------

def probar_reintentos(conf: dict, esc: Escenario) -> list[dict]:
    """Manda 3 comentarios dos veces cada uno, con la misma clave de idempotencia,
    como haria un celular que no recibio la respuesta. Fuera de las metricas."""
    resultado = []
    with httpx.Client(base_url=f"http://127.0.0.1:{conf['PUERTO_API']}", timeout=10) as cliente:
        for k in range(3):
            clave = f"{esc.run_id}-reintento-{k}"
            cuerpo = {"usuario_id": "carga-reintentos", "usuario_nombre": "reintentos",
                      "contenido": f"[{esc.run_id}] reintento {k}", "clave_idempotencia": clave}
            ids = []
            for _ in range(2):
                r = cliente.post(f"/partidos/{esc.partido}/comentarios", params={"bloque_horario": esc.bloque_actual}, json=cuerpo)
                ids.append(r.json().get("comentario_id") if r.status_code == 201 else f"http_{r.status_code}")
            resultado.append({"clave": clave, "ids": ids})
    return resultado


# --- Resumen ------------------------------------------------------------------

def resumir(ops: list) -> dict:
    ok = sorted(o[2] for o in ops if not o[3])
    errores = {}
    for o in ops:
        if o[3]:
            errores[o[3]] = errores.get(o[3], 0) + 1
    r = {"ops": len(ops), "ok": len(ok), "errores": sum(errores.values()), "errores_por_tipo": errores}
    if ok:
        r.update(min=ok[0], p50=percentil(ok, 50), p90=percentil(ok, 90), p95=percentil(ok, 95),
                 p99=percentil(ok, 99), max=ok[-1], promedio=sum(ok) / len(ok))
        r = {k: round(v, 1) if isinstance(v, float) else v for k, v in r.items()}
    return r


def metricas(gen: Generador) -> dict:
    duraciones = {"calentamiento": gen.cal, "rampa": gen.rampa, "sostenimiento": gen.sost}
    salida = {}
    for fase in FASES:
        ops_fase = [o for o in gen.ops if gen.fase(o[0]) == fase]
        if not ops_fase:
            continue
        duracion = duraciones[fase]
        if gen.parar.is_set():  # corrida cortada: la fase duro menos que lo configurado
            inicio = sum(duraciones[f] for f in FASES[:FASES.index(fase)])
            duracion = min(duracion, max(o[0] for o in ops_fase) - inicio) or duracion
        salida[fase] = {"duracion_s": round(duracion, 1)}
        for tipo in TIPOS + ("total",):
            sel = ops_fase if tipo == "total" else [o for o in ops_fase if o[1] == tipo]
            res = resumir(sel)
            res["ok_por_s"] = round(res["ok"] / duracion, 1)
            salida[fase][tipo] = res
    return salida


def evolucion(gen: Generador) -> list[dict]:
    """Cada 5 s: operaciones por segundo, p95 y errores (para ver si la prueba fue estable)."""
    filas = []
    fin = max((o[0] for o in gen.ops), default=0)
    for inicio in range(0, int(fin) + 1, 5):
        sel = [o for o in gen.ops if inicio <= o[0] < inicio + 5]
        ok = sorted(o[2] for o in sel if not o[3])
        filas.append({"t": inicio, "fase": gen.fase(inicio), "ops_por_s": round(len(sel) / 5, 1),
                      "p95_ms": round(percentil(ok, 95), 1), "errores": sum(1 for o in sel if o[3])})
    return filas


def promedio_y_maximo(muestras: list, clave: str) -> str:
    valores = [m[clave] for m in muestras if clave in m]
    return f"{sum(valores) / len(valores):.0f} / {max(valores):.0f}" if valores else "no medido"


def texto_resultados(r: dict) -> str:
    c, e, v = r["configuracion"], r["entorno"], r["version"]
    sin_commit = (f"{len(v['sin_commitear'])} archivos sin commitear: {', '.join(v['sin_commitear'])}"
                  if v["sin_commitear"] else "sin cambios sin commitear")
    lineas = [
        f"Hito 12 - prueba de carga | modo: {r['modo']} (INFLUX_REUSAR_CLIENTE={MODOS[r['modo']]}) | corrida {r['run_id']}",
        f"Fecha: {r['fecha']} | commit: {v['commit']} ({sin_commit})",
        f"Entorno: {e['sistema']}, {e['cpu_logicas']} CPU logicas, {e['ram_total']} de RAM, Python {e['python']}; "
        + ", ".join(f"{k} {val}" for k, val in e["librerias"].items()),
        "Imagenes: " + " | ".join(f"{k}: {val}" for k, val in e["imagenes"].items()),
        f"Escenario: {c['USUARIOS_VIRTUALES']} usuarios virtuales x {c['OPS_POR_USUARIO_S']} ops/s = "
        f"{r['tasa_objetivo']:.0f} ops/s objetivo; calentamiento {c['CALENTAMIENTO_S']} s, rampa {c['RAMPA_S']} s, "
        f"sostenimiento {c['SOSTENIMIENTO_S']} s; mezcla {c['MEZCLA_LEER_COMENTARIOS']}/{c['MEZCLA_PUBLICAR_COMENTARIO']}/"
        f"{c['MEZCLA_LEER_ESTADISTICAS']} (leer comentarios/publicar/leer estadisticas); timeout {c['TIMEOUT_REQUEST_S']} s",
        f"Datos: partido {c['PARTIDO']} minuto 60 (bloque {r['bloque_actual']}); keyspace {c['KEYSPACE_PRUEBA']}, "
        f"base InfluxDB {c['INFLUX_DB_PRUEBA']} (ver preparacion_datos.txt)",
        f"Resultado de la corrida: {r['estado']}",
        "Medicion: latencia = tiempo de cada request visto por el generador (ms, solo respuestas correctas);",
        "  una respuesta es correcta si tiene el status esperado Y el contenido esperado (cantidad de items, id).",
        "",
    ]
    for fase in FASES:
        if fase not in r["metricas"]:
            continue
        m = r["metricas"][fase]
        titulo = "lo que se compara" if fase == "sostenimiento" else "no se compara"
        lineas += [f"== {fase.capitalize()} ({m['duracion_s']} s, {titulo})",
                   f"{'operacion':22}{'ops':>6}{'ok':>6}{'err':>5}{'ok/s':>7}{'min':>7}{'p50':>7}{'p90':>7}{'p95':>7}{'p99':>8}{'max':>8}  (ms)"]
        for tipo in TIPOS + ("total",):
            x = m[tipo]
            if not x["ops"]:
                continue
            lineas.append(f"{tipo:22}{x['ops']:>6}{x['ok']:>6}{x['errores']:>5}{x['ok_por_s']:>7}"
                          + "".join(f"{x.get(k, 0):>7}" for k in ("min", "p50", "p90", "p95"))
                          + "".join(f"{x.get(k, 0):>8}" for k in ("p99", "max")))
        errores = m["total"]["errores_por_tipo"]
        lineas.append(f"errores: {errores if errores else 'ninguno'}")
        lineas.append("")
    sost = [s for s in r["recursos"] if s["fase"] == "sostenimiento"]
    lineas += [f"Tasa objetivo {r['tasa_objetivo']:.0f} ops/s; lograda en sostenimiento "
               f"{r['metricas'].get('sostenimiento', {}).get('total', {}).get('ops', 0) / max(float(c['SOSTENIMIENTO_S']), 1):.1f} ops/s; "
               f"operaciones que salieron tarde porque la anterior no habia respondido: {r['ops_atrasadas']}",
               "",
               f"== Recursos durante el sostenimiento ({len(sost)} muestras cada {PAUSA_RECURSOS_S} s; promedio / maximo)",
               f"API (uvicorn, 1 proceso):   CPU {promedio_y_maximo(sost, 'api_cpu_pct')} %  (100 % = 1 nucleo), "
               f"memoria {promedio_y_maximo(sost, 'api_mem_mb')} MB",
               f"Generador de carga:         CPU {promedio_y_maximo(sost, 'generador_cpu_pct')} %",
               f"Contenedor h10-cassandra:   CPU {promedio_y_maximo(sost, 'cassandra_cpu_pct')} %, "
               f"memoria {promedio_y_maximo(sost, 'cassandra_mem_mb')} MB",
               f"Contenedor h10-influxdb:    CPU {promedio_y_maximo(sost, 'influxdb_cpu_pct')} %, "
               f"memoria {promedio_y_maximo(sost, 'influxdb_mem_mb')} MB",
               "",
               "== Evolucion cada 5 s",
               f"{'t (s)':>6}  {'fase':14}{'ops/s':>7}{'p95 ms':>9}{'errores':>9}"]
    lineas += [f"{f['t']:>6}  {f['fase']:14}{f['ops_por_s']:>7}{f['p95_ms']:>9}{f['errores']:>9}" for f in r["evolucion"]]
    e = r["escrituras"]
    lineas += ["", f"Escrituras: {e['aceptados']} aceptadas (201), {e['rechazados']} rechazadas, "
               f"{e['desconocidos']} sin respuesta. La verificacion contra Cassandra esta en integridad_{r['modo']}.txt"]
    return "\n".join(lineas) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modo", choices=MODOS, required=True)
    modo = parser.parse_args().modo
    conf = configuracion()
    puerto = int(conf["PUERTO_API"])
    if puerto_ocupado(puerto):
        sys.exit(f"ERROR: el puerto {puerto} ya esta en uso. Cerrar lo que lo use o cambiar PUERTO_API en config/local.env.")
    if psutil is None:
        print("AVISO: falta psutil (pip install psutil): no se va a medir CPU ni memoria de la API.")

    TRABAJO.mkdir(exist_ok=True)
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    run_id = f"{modo[:2]}{datetime.now().strftime('%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
    print(f"Levantando la API de prueba en el puerto {puerto} (modo {modo}, INFLUX_REUSAR_CLIENTE={MODOS[modo]})...")
    log = open(TRABAJO / f"api_{modo}.log", "w", encoding="utf-8")
    api = levantar_api(modo, conf, log)
    try:
        esc = Escenario(conf, run_id)
        # Antes de cargar: una operacion de cada tipo tiene que andar; si no, faltan datos o algo esta caido
        with httpx.Client(base_url=f"http://127.0.0.1:{puerto}", timeout=10) as c:
            fallas = [t for t in ("leer_comentarios", "leer_estadisticas") if getattr(esc, t)(c, random.Random(0), 0, 0)]
        if fallas:
            sys.exit(f"ERROR: {fallas} no devuelve lo esperado. Correr antes: python scripts/preparar_datos.py")
        gen = Generador(conf, esc)
        print(f"Corriendo la carga: {gen.vus} usuarios virtuales, "
              f"{gen.cal + gen.rampa + gen.sost:.0f} s en total. Ctrl+C la corta y guarda lo medido.")
        muestreador = Muestreador(api)
        estado = gen.correr(muestreador)
        reintentos = probar_reintentos(conf, esc) if estado == "completa" else []
    finally:
        detener_api(api)
        log.close()

    resultados = {
        "modo": modo, "run_id": run_id, "fecha": ahora(), "estado": estado,
        "version": version_codigo(), "entorno": entorno(), "configuracion": conf,
        "tasa_objetivo": gen.vus * float(conf["OPS_POR_USUARIO_S"]), "bloque_actual": esc.bloque_actual,
        "metricas": metricas(gen), "ops_atrasadas": gen.atrasadas,
        "recursos": muestreador.muestras, "evolucion": evolucion(gen),
        "escrituras": {"aceptados": len(esc.aceptados), "rechazados": len(esc.rechazados),
                       "desconocidos": len(esc.desconocidos)},
    }
    # Los ids escritos quedan en trabajo/ (no se versiona) para validar_integridad.py
    (TRABAJO / f"escrituras_{modo}.json").write_text(json.dumps({
        "run_id": run_id, "partido": esc.partido, "bloque": esc.bloque_actual, "aceptados": esc.aceptados,
        "rechazados": esc.rechazados, "desconocidos": esc.desconocidos, "reintentos": reintentos}), encoding="utf-8")
    (EVIDENCIA / f"resultados_{modo}.json").write_text(json.dumps(resultados, indent=1, ensure_ascii=False), encoding="utf-8")
    texto = texto_resultados(resultados)
    (EVIDENCIA / f"resultados_{modo}.txt").write_text(texto, encoding="utf-8")
    print()
    print(texto)
    print(f"-> docs/evidencia/resultados_{modo}.txt y .json")
    if estado != "completa":
        sys.exit(1)


if __name__ == "__main__":
    main()
