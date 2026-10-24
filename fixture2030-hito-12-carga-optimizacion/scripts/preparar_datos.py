# -*- coding: utf-8 -*-
"""Hito 12 - Preparacion de los datos de laboratorio.

Crea un keyspace de Cassandra y una base de InfluxDB propios de la prueba
(no toca los datos del Hito 10) y carga un partido completo, F2030-006:
  - Cassandra: 21 bloques de 5 minutos x COMENTARIOS_POR_BLOQUE comentarios,
    con el mismo esquema del Hito 6 (se lee de scripts/cassandra/esquema.cql).
  - InfluxDB: 1 muestra por segundo por equipo durante 105 minutos (Hito 8).

Los datos son sinteticos y deterministicos (semilla fija): correrlo de nuevo
reescribe las mismas filas y los mismos puntos, no duplica nada.
"""

import random
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from cassandra.cluster import Cluster
from cassandra.concurrent import execute_concurrent_with_args

from comun import (DURACION_S, EQUIPOS, EVIDENCIA, HITO10, INICIO_PARTIDO, ahora, bloque, configuracion,
                   env_hito10, version_codigo)

SEMILLA = 2030
NAMESPACE = uuid.UUID("6ea1f0c0-0000-4000-8000-000000000012")
FRASES = ["Que golazo!", "Vamos todavia", "Penal clarisimo", "El arbitro no ve nada", "Que atajada",
          "Hay que meter mas presion", "Cambio ya", "Ese pase fue una locura", "Se viene el gol", "Aguante"]


# --- Cassandra ----------------------------------------------------------------

def crear_keyspace(sesion, keyspace: str) -> None:
    """Ejecuta el esquema del Hito 6 (el mismo que usa el Hito 10) cambiando solo el keyspace."""
    texto = (HITO10 / "scripts" / "cassandra" / "esquema.cql").read_text(encoding="utf-8")
    texto = "\n".join(l for l in texto.splitlines() if not l.strip().startswith("--"))
    for sentencia in re.split(r";\s*$", texto, flags=re.M):  # ";" al final de linea (hay ";" dentro de los comment)
        sentencia = re.sub(r"\bfixture2030\b", keyspace, sentencia.strip())
        if not sentencia or sentencia.upper().startswith("DESCRIBE"):
            continue
        if sentencia.upper().startswith("USE "):
            sesion.set_keyspace(keyspace)
        else:
            sesion.execute(sentencia)


def generar_comentarios(partido: str, por_bloque: int) -> list[tuple]:
    rng = random.Random(SEMILLA)
    hinchas = [f"hincha-{i:04d}" for i in range(1, 2001)]
    pesos = [1 / (i ** 0.8) for i in range(1, 2001)]  # pocos hinchas comentan mucho, la mayoria poco
    filas = []
    for b in range(DURACION_S // 300):
        usuarios = rng.choices(hinchas, weights=pesos, k=por_bloque)
        for k in range(por_bloque):
            creado_en = INICIO_PARTIDO + timedelta(seconds=b * 300 + rng.randrange(300), milliseconds=rng.randrange(1000))
            comentario_id = uuid.uuid5(NAMESPACE, f"semilla|{partido}|{b}|{k}")
            contenido = f"[semilla] {rng.choice(FRASES)}"
            filas.append((partido, bloque(b * 300), creado_en, comentario_id, usuarios[k], usuarios[k],
                          contenido, "visible", int(rng.expovariate(0.2)), 0))
    return filas


def cargar_cassandra(env: dict, conf: dict) -> list[str]:
    keyspace, partido = conf["KEYSPACE_PRUEBA"], conf["PARTIDO"]
    cluster = Cluster(env.get("CASSANDRA_HOSTS", "127.0.0.1").split(","), port=int(env.get("CASSANDRA_PORT", "9042")))
    sesion = cluster.connect()
    sesion.default_timeout = 30
    crear_keyspace(sesion, keyspace)
    filas = generar_comentarios(partido, int(conf["COMENTARIOS_POR_BLOQUE"]))
    por_bloque = sesion.prepare(
        "INSERT INTO comentarios_por_bloque (partido_id, bloque_horario, creado_en, comentario_id, usuario_id, "
        "usuario_nombre, contenido, estado, likes, reportes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
    por_usuario = sesion.prepare(
        "INSERT INTO comentarios_por_usuario (usuario_id, creado_en, comentario_id, partido_id, contenido) "
        "VALUES (?, ?, ?, ?, ?)")
    fallidas = 0
    for ok, _ in execute_concurrent_with_args(sesion, por_bloque, filas, concurrency=50, raise_on_first_error=False):
        fallidas += not ok
    filas_usuario = [(f[4], f[2], f[3], f[0], f[6]) for f in filas]
    for ok, _ in execute_concurrent_with_args(sesion, por_usuario, filas_usuario, concurrency=50, raise_on_first_error=False):
        fallidas += not ok

    # Validacion: se cuenta cada particion de vuelta (no se confia en que el INSERT haya respondido OK)
    contados = 0
    for b in range(DURACION_S // 300):
        resultado = sesion.execute(
            "SELECT contenido FROM comentarios_por_bloque WHERE partido_id = %s AND bloque_horario = %s",
            (partido, bloque(b * 300)))
        contados += sum(1 for f in resultado if f.contenido.startswith("[semilla]"))
    cluster.shutdown()
    estado = "OK" if contados == len(filas) and fallidas == 0 else "FALLA"
    return [f"[{estado}] Cassandra keyspace {keyspace}: {len(filas)} comentarios generados en {DURACION_S // 300} bloques, "
            f"{fallidas} inserts fallidos, {contados} leidos de vuelta en comentarios_por_bloque"]


# --- InfluxDB -----------------------------------------------------------------

def generar_puntos(partido: str) -> list[str]:
    rng = random.Random(SEMILLA)
    posesion, pases, tiros = 50.0, {"ARG": 0, "ESP": 0}, {"ARG": 0, "ESP": 0}
    epoch0 = int(INICIO_PARTIDO.timestamp())
    lineas = []
    for s in range(DURACION_S):
        posesion = min(70.0, max(30.0, posesion + rng.uniform(-0.4, 0.4)))
        for equipo in EQUIPOS:
            pct = posesion if equipo == "ARG" else 100 - posesion
            pases[equipo] += rng.random() < pct / 100 * 0.3
            tiros[equipo] += rng.random() < 0.002
            lineas.append(f"estadisticas,partido_id={partido},equipo_id={equipo},sede=BUE "
                          f"posesion_pct={pct:.1f},pases_completados={pases[equipo]}i,tiros={tiros[equipo]}i {epoch0 + s}")
    return lineas


def cargar_influx(env: dict, conf: dict) -> list[str]:
    base, partido = conf["INFLUX_DB_PRUEBA"], conf["PARTIDO"]
    url = env.get("INFLUX_URL", "http://127.0.0.1:8181")
    cliente = httpx.Client(headers={"Authorization": f"Bearer {env['INFLUX_TOKEN']}"}, timeout=30)
    r = cliente.post(f"{url}/api/v3/configure/database", json={"db": base})
    if r.status_code not in (200, 201, 204, 409):
        sys.exit(f"ERROR: InfluxDB no creo la base {base}: HTTP {r.status_code} {r.text[:200]}")
    lineas = generar_puntos(partido)
    lotes_fallidos = 0
    for i in range(0, len(lineas), 5000):
        r = cliente.post(f"{url}/api/v3/write_lp", params={"db": base, "precision": "second"},
                         content="\n".join(lineas[i:i + 5000]))
        lotes_fallidos += r.status_code >= 300
    r = cliente.post(f"{url}/api/v3/query_sql", json={
        "db": base, "format": "json",
        "q": f"SELECT equipo_id, COUNT(*) AS puntos FROM estadisticas WHERE partido_id = '{partido}' GROUP BY equipo_id ORDER BY equipo_id"})
    conteo = {f["equipo_id"]: f["puntos"] for f in r.json()} if r.status_code == 200 else {}
    estado = "OK" if lotes_fallidos == 0 and all(conteo.get(e) == DURACION_S for e in EQUIPOS) else "FALLA"
    return [f"[{estado}] InfluxDB base {base}: {len(lineas)} puntos en lotes de 5000, {lotes_fallidos} lotes fallidos, "
            f"leidos de vuelta por equipo: {conteo}"]


def main() -> None:
    conf, env = configuracion(), env_hito10()
    version = version_codigo()
    print("Preparando datos de laboratorio (puede tardar 1 o 2 minutos)...")
    lineas = [f"Hito 12 - preparacion de datos | {ahora()} | commit {version['commit']}",
              f"Partido {conf['PARTIDO']} (ARG vs ESP), {DURACION_S} s de juego desde {INICIO_PARTIDO.isoformat()}",
              *cargar_cassandra(env, conf), *cargar_influx(env, conf)]
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    (EVIDENCIA / "preparacion_datos.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    if any("[FALLA]" in l for l in lineas):
        sys.exit(1)


if __name__ == "__main__":
    main()
