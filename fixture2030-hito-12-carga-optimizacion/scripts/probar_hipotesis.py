# -*- coding: utf-8 -*-
"""Hito 12 - Prueba aislada de la hipotesis del cuello de botella.

Hipotesis: la ruta de estadisticas es lenta porque el adaptador de InfluxDB
crea un httpx.Client nuevo en cada consulta (httpx.post), y crear el cliente
cuesta mas CPU que la consulta misma. Para separarlo de la API, se mide:
  1. cuanto tarda solo crear un cliente;
  2. la misma consulta del flujo con un cliente nuevo cada vez (como el Hito 10);
  3. la misma consulta reutilizando un cliente.
Sin concurrencia, 50 repeticiones de cada una. Guarda docs/evidencia/prueba_hipotesis.txt
"""

import time

import httpx

from comun import EVIDENCIA, INICIO_PARTIDO, MOMENTO_ACTUAL_S, ahora, configuracion, env_hito10, percentil, version_codigo

REPETICIONES = 50


def medir(funcion) -> list[float]:
    tiempos = []
    for _ in range(REPETICIONES):
        inicio = time.perf_counter()
        funcion()
        tiempos.append((time.perf_counter() - inicio) * 1000)
    return sorted(tiempos)


def main() -> None:
    conf, env = configuracion(), env_hito10()
    fin = int(INICIO_PARTIDO.timestamp()) + MOMENTO_ACTUAL_S
    sql = ("SELECT time, equipo_id, posesion_pct, pases_completados, tiros FROM estadisticas "
           f"WHERE partido_id = '{conf['PARTIDO']}' AND equipo_id = 'ARG' "
           f"AND time >= to_timestamp_seconds({fin - 300}) AND time < to_timestamp_seconds({fin}) ORDER BY time LIMIT 300")
    url = f"{env.get('INFLUX_URL', 'http://127.0.0.1:8181')}/api/v3/query_sql"
    pedido = dict(headers={"Authorization": f"Bearer {env['INFLUX_TOKEN']}"},
                  json={"db": conf["INFLUX_DB_PRUEBA"], "q": sql, "format": "json"}, timeout=10)

    filas = len(httpx.post(url, **pedido).json())  # tambien sirve de calentamiento
    compartido = httpx.Client()
    casos = [
        ("crear httpx.Client() (sin consultar)", lambda: httpx.Client().close()),
        ("consulta con cliente nuevo (httpx.post, Hito 10)", lambda: httpx.post(url, **pedido)),
        ("consulta con cliente reutilizado", lambda: compartido.post(url, **pedido)),
    ]
    lineas = [f"Hito 12 - prueba de la hipotesis | {ahora()} | commit {version_codigo()['commit']}",
              f"{REPETICIONES} repeticiones de cada caso, una por vez (sin concurrencia). La consulta devuelve {filas} filas.",
              "Tiempo de pared medido con time.perf_counter() en este proceso, en ms.", "",
              f"{'caso':52}{'p50':>8}{'p95':>8}{'max':>8}"]
    for nombre, funcion in casos:
        t = medir(funcion)
        lineas.append(f"{nombre:52}{percentil(t, 50):>8.1f}{percentil(t, 95):>8.1f}{t[-1]:>8.1f}")
    compartido.close()
    texto = "\n".join(lineas) + "\n"
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    (EVIDENCIA / "prueba_hipotesis.txt").write_text(texto, encoding="utf-8")
    print(texto)
    print("-> docs/evidencia/prueba_hipotesis.txt")


if __name__ == "__main__":
    main()
