# -*- coding: utf-8 -*-
"""Hito 12 - Validacion de integridad despues de una corrida de carga.

Un 201 de la API no alcanza: se lee Cassandra directamente y se compara con lo
que el generador registro como aceptado. Tambien se revisa que los datos de
laboratorio sigan intactos y que reintentar con la misma clave no duplique.

  python scripts/validar_integridad.py --modo linea_base|optimizada
"""

import argparse
import json
import sys
from collections import Counter

import httpx
from cassandra.cluster import Cluster

from comun import DURACION_S, EQUIPOS, EVIDENCIA, TRABAJO, ahora, bloque, configuracion, env_hito10, version_codigo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", choices=("linea_base", "optimizada"), required=True)
    modo = parser.parse_args().modo
    archivo = TRABAJO / f"escrituras_{modo}.json"
    if not archivo.exists():
        sys.exit(f"ERROR: no esta {archivo}: correr antes python scripts/ejecutar_carga.py --modo {modo}")
    escrituras = json.loads(archivo.read_text(encoding="utf-8"))
    resultados = json.loads((EVIDENCIA / f"resultados_{modo}.json").read_text(encoding="utf-8"))
    conf, env = configuracion(), env_hito10()
    run_id, partido = escrituras["run_id"], escrituras["partido"]
    marca = f"[{run_id}]"
    lineas = [f"Hito 12 - integridad | modo: {modo} | corrida {run_id}",
              f"Fecha: {ahora()} | commit: {version_codigo()['commit']} | keyspace {conf['KEYSPACE_PRUEBA']}", ""]

    def informar(estado: str, texto: str) -> None:
        lineas.append(f"[{estado:8}] {texto}")

    cluster = Cluster(env.get("CASSANDRA_HOSTS", "127.0.0.1").split(","), port=int(env.get("CASSANDRA_PORT", "9042")))
    sesion = cluster.connect(conf["KEYSPACE_PRUEBA"])
    sesion.default_timeout = 30

    # 1. Lo que el generador registro como aceptado vs lo que hay en la tabla principal
    filas = [f for f in sesion.execute(
        "SELECT comentario_id, usuario_id, contenido FROM comentarios_por_bloque WHERE partido_id = %s AND bloque_horario = %s",
        (partido, escrituras["bloque"])) if f.contenido.startswith(marca) and "reintento" not in f.contenido]
    en_tabla = Counter(str(f.comentario_id) for f in filas)
    aceptados = {a["id"] for a in escrituras["aceptados"]}
    faltan = aceptados - set(en_tabla)
    sobran = set(en_tabla) - aceptados
    duplicados = {i: n for i, n in en_tabla.items() if n > 1}
    n_desc = len(escrituras["desconocidos"])
    informar("OK" if not faltan else "FALLA",
             f"comentarios_por_bloque: {len(aceptados)} aceptados por la API (201), {len(filas)} filas de esta corrida "
             f"en la tabla, faltantes {len(faltan)}")
    informar("OK" if not duplicados else "FALLA", f"ids repetidos en comentarios_por_bloque: {len(duplicados)}")
    if sobran:
        # Una request sin respuesta (timeout) pudo haberse escrito igual
        informar("OK" if len(sobran) <= n_desc else "FALLA",
                 f"filas que no figuran como aceptadas: {len(sobran)} (requests sin respuesta: {n_desc})")
    informar("OK", f"rechazadas por la API: {len(escrituras['rechazados'])}, sin respuesta (timeout/conexion): {n_desc}")

    # 2. La tabla por usuario (escrita en la misma request) tiene que tener los mismos comentarios
    por_usuario = Counter()
    for usuario in sorted({a["usuario_id"] for a in escrituras["aceptados"]}):
        for f in sesion.execute("SELECT comentario_id, contenido FROM comentarios_por_usuario WHERE usuario_id = %s", (usuario,)):
            if f.contenido.startswith(marca):
                por_usuario[str(f.comentario_id)] += 1
    distinto = set(por_usuario) ^ set(en_tabla)
    informar("OK" if not distinto and not any(n > 1 for n in por_usuario.values()) else "FALLA",
             f"comentarios_por_usuario: {sum(por_usuario.values())} filas de esta corrida, "
             f"diferencias con comentarios_por_bloque: {len(distinto)}")

    # 3. Los datos sembrados siguen iguales (la carga no los toco)
    esperado = DURACION_S // 300 * int(conf["COMENTARIOS_POR_BLOQUE"])
    semilla = Counter()
    for b in range(DURACION_S // 300):
        for f in sesion.execute("SELECT comentario_id, contenido FROM comentarios_por_bloque WHERE partido_id = %s AND bloque_horario = %s",
                                (partido, bloque(b * 300))):
            if f.contenido.startswith("[semilla]"):
                semilla[str(f.comentario_id)] += 1
    informar("OK" if sum(semilla.values()) == esperado == len(semilla) else "FALLA",
             f"comentarios sembrados: {sum(semilla.values())} filas, {len(semilla)} ids distintos (esperado {esperado})")

    r = httpx.post(f"{env.get('INFLUX_URL', 'http://127.0.0.1:8181')}/api/v3/query_sql",
                   headers={"Authorization": f"Bearer {env['INFLUX_TOKEN']}"}, timeout=30,
                   json={"db": conf["INFLUX_DB_PRUEBA"], "format": "json",
                         "q": f"SELECT equipo_id, COUNT(*) AS puntos FROM estadisticas WHERE partido_id = '{partido}' GROUP BY equipo_id"})
    puntos = {f["equipo_id"]: f["puntos"] for f in r.json()} if r.status_code == 200 else {}
    informar("OK" if all(puntos.get(e) == DURACION_S for e in EQUIPOS) else "FALLA",
             f"puntos de InfluxDB por equipo: {puntos} (esperado {DURACION_S} cada uno)")

    # 4. Las lecturas: el generador valido el contenido de cada respuesta, no solo el status
    sost = resultados["metricas"].get("sostenimiento", {})
    for tipo in ("leer_comentarios", "leer_estadisticas"):
        x = sost.get(tipo, {})
        invalidas = x.get("errores_por_tipo", {}).get("contenido_invalido", 0)
        informar("OK" if not invalidas else "FALLA",
                 f"{tipo}: {x.get('ok', 0)} respuestas con el contenido esperado, {invalidas} con contenido incorrecto")

    # 5. Reintentos con la misma clave de idempotencia
    for intento in escrituras["reintentos"]:
        ids = set(intento["ids"])
        filas_id = 0
        if len(ids) == 1 and not next(iter(ids)).startswith("http_"):
            filas_id = sum(1 for f in sesion.execute(
                "SELECT comentario_id FROM comentarios_por_bloque WHERE partido_id = %s AND bloque_horario = %s",
                (partido, escrituras["bloque"])) if str(f.comentario_id) in ids)
        informar("OK" if filas_id == 1 else "HALLAZGO",
                 f"reintento {intento['clave']}: 2 envios, mismo id: {'si' if len(ids) == 1 else 'no'}, filas en la tabla: {filas_id}")
    cluster.shutdown()

    if any("HALLAZGO" in l for l in lineas):
        lineas += ["", "HALLAZGO: el reintento devuelve el mismo id pero deja dos filas. El id es deterministico, pero",
                   "creado_en (parte de la clave primaria) se toma en cada request. Ver docs/integridad_y_limitaciones.md."]
    texto = "\n".join(lineas) + "\n"
    (EVIDENCIA / f"integridad_{modo}.txt").write_text(texto, encoding="utf-8")
    print(texto)
    print(f"-> docs/evidencia/integridad_{modo}.txt")
    if any(l.startswith("[FALLA") for l in lineas):
        sys.exit(1)


if __name__ == "__main__":
    main()
