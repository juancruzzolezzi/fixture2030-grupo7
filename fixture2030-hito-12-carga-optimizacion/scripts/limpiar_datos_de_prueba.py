# -*- coding: utf-8 -*-
"""Hito 12 - Limpieza opcional de los datos de laboratorio.

Borra solo lo que creo esta prueba: el keyspace KEYSPACE_PRUEBA de Cassandra,
la base INFLUX_DB_PRUEBA de InfluxDB y la carpeta trabajo/. No toca los datos
del Hito 10, los volumenes de Docker ni docs/evidencia/.

  python scripts/limpiar_datos_de_prueba.py --confirmar
"""

import argparse
import shutil
import sys

import httpx
from cassandra.cluster import Cluster

from comun import TRABAJO, configuracion, env_hito10


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirmar", action="store_true", help="sin esto solo muestra lo que borraria")
    confirmar = parser.parse_args().confirmar
    conf, env = configuracion(), env_hito10()
    keyspace, base = conf["KEYSPACE_PRUEBA"], conf["INFLUX_DB_PRUEBA"]
    if keyspace == "fixture2030" or base == "fixture2030_series":
        sys.exit("ERROR: la configuracion apunta a los datos del Hito 10; no se borra nada.")
    print(f"Se borraria: keyspace Cassandra '{keyspace}', base InfluxDB '{base}' y la carpeta trabajo/")
    if not confirmar:
        print("No se borro nada. Para borrar: python scripts/limpiar_datos_de_prueba.py --confirmar")
        return
    cluster = Cluster(env.get("CASSANDRA_HOSTS", "127.0.0.1").split(","), port=int(env.get("CASSANDRA_PORT", "9042")))
    sesion = cluster.connect()
    sesion.default_timeout = 60
    sesion.execute(f"DROP KEYSPACE IF EXISTS {keyspace}")
    cluster.shutdown()
    r = httpx.delete(f"{env.get('INFLUX_URL', 'http://127.0.0.1:8181')}/api/v3/configure/database", params={"db": base},
                     headers={"Authorization": f"Bearer {env['INFLUX_TOKEN']}"}, timeout=30)
    print(f"Cassandra: keyspace {keyspace} borrado | InfluxDB: base {base} -> HTTP {r.status_code}")
    shutil.rmtree(TRABAJO, ignore_errors=True)
    print("Listo. Para volver a probar: bash scripts/ejecutar_linea_base.sh (vuelve a preparar los datos).")


if __name__ == "__main__":
    main()
