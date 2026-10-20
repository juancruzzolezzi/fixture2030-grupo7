"""
Hito 11 - Evaluacion de conectividad de la API del Hito 10 con sus 6 bases.

Recorre las capas de menor a mayor costo:
  configuracion -> DNS -> TCP -> protocolo/autenticacion -> contexto -> lectura -> API

Uso (con el venv de la API del Hito 10, que ya tiene todos los drivers):
  ../fixture2030-hito-10-api-integrada/.venv/bin/python scripts/evaluar_conectividad.py
  ... --modo tcp | nativos | api        (por defecto: completo)
  ... --producto redis                  (una sola dependencia)

La conexion a las bases sale del .env del Hito 10 (el mismo que usa la API).
config/local.env (copia de config/configuracion-ejemplo.env) agrega lo propio
de la evaluacion: URL de la API, portales HTTP y timeout.

Resultados: OK = la prueba funciono | FALLA = se ejecuto y fallo |
SKIP = no se ejecuto porque falta una herramienta o configuracion (NO quiere
decir que el producto este caido) | N/A = la capa no aplica en el laboratorio |
NO_EJECUTADA = fallo una capa anterior.

Todas las pruebas son de lectura: no se borra ni modifica nada.
"""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

HITO11 = Path(__file__).resolve().parent.parent
HITO10 = HITO11.parent / "fixture2030-hito-10-api-integrada"
EVIDENCIA = HITO11 / "docs" / "evidencia"
SECRETOS = ("NEO4J_PASSWORD", "IRIS_PASSWORD", "INFLUX_TOKEN")


# ----------------------------------------------------------------------------- configuracion

def cargar_env(ruta: Path):
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip())


def env(nombre, default=""):
    return os.environ.get(nombre, default).strip()


def ocultar(texto: str) -> str:
    """Saca passwords y tokens de cualquier texto antes de mostrarlo o guardarlo."""
    texto = re.sub(r"(://[^:/@\s]+:)[^@\s]+@", r"\1***@", str(texto))  # password dentro de una URI
    for nombre in SECRETOS:
        valor = env(nombre)
        if len(valor) >= 3:  # solo palabras completas: IRIS usa "SYS" y no hay que tapar "%SYSTEM"
            texto = re.sub(rf"(?<![\w%]){re.escape(valor)}(?!\w)", "***", texto)
    return texto


def dependencias():
    mongo = urlparse(env("MONGO_URI"))
    neo = urlparse(env("NEO4J_URI", "bolt://localhost:7687"))
    neo_http = urlparse(env("NEO4J_HTTP_URL", "http://localhost:7474"))
    influx = urlparse(env("INFLUX_URL", "http://localhost:8181"))
    iris_portal = urlparse(env("IRIS_PORTAL_URL", "http://localhost:52773"))
    return {
        "mongodb": (mongo.hostname, mongo.port or 27017, "MONGO_URI"),
        "neo4j": (neo.hostname, neo.port or 7687, "NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD"),
        "neo4j-http": (neo_http.hostname, neo_http.port or 7474, "NEO4J_HTTP_URL"),
        "cassandra": (env("CASSANDRA_HOSTS", "localhost").split(",")[0], int(env("CASSANDRA_PORT", "9042")), "CASSANDRA_HOSTS, CASSANDRA_KEYSPACE"),
        "redis": (env("REDIS_HOST", "localhost"), int(env("REDIS_PORT", "6379")), "REDIS_HOST, REDIS_PORT"),
        "influxdb": (influx.hostname, influx.port or 8181, "INFLUX_URL, INFLUX_DATABASE, INFLUX_TOKEN"),
        "iris": (env("IRIS_HOST", "localhost"), int(env("IRIS_PORT", "1972")), "IRIS_HOST, IRIS_NAMESPACE, IRIS_USER, IRIS_PASSWORD"),
        "iris-portal": (iris_portal.hostname, iris_portal.port or 52773, "IRIS_PORTAL_URL"),
    }


# ----------------------------------------------------------------------------- registro de resultados

class Registro:
    def __init__(self, nombre):
        self.nombre = nombre
        self.filas = []
        self.lineas = []
        self.escribir(f"Hito 11 - {nombre}")
        self.escribir(f"Fecha: {datetime.now().astimezone().isoformat(timespec='seconds')} | commit: {commit()} | "
                      f"entorno: notebook (API fuera de Docker, bases en Docker Compose)")
        self.escribir("-" * 110)

    def escribir(self, texto=""):
        texto = ocultar(texto)
        print(texto)
        self.lineas.append(texto)

    def agregar(self, dep, capa, resultado, detalle, ms=None):
        self.filas.append({"dependencia": dep, "capa": capa, "resultado": resultado, "detalle": ocultar(detalle), "ms": ms})
        tiempo = f"{ms:8.1f} ms" if ms is not None else " " * 11
        self.escribir(f"[{resultado:<12}] {dep:<12} {capa:<14} {tiempo}  {detalle}")

    def guardar(self, archivo):
        EVIDENCIA.mkdir(parents=True, exist_ok=True)
        conteo = {}
        for f in self.filas:
            conteo[f["resultado"]] = conteo.get(f["resultado"], 0) + 1
        self.escribir("-" * 110)
        self.escribir("Resumen: " + ", ".join(f"{k}={v}" for k, v in sorted(conteo.items())))
        (EVIDENCIA / f"{archivo}.txt").write_text("\n".join(self.lineas) + "\n", encoding="utf-8")
        (EVIDENCIA / f"{archivo}.json").write_text(json.dumps(self.filas, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"-> docs/evidencia/{archivo}.txt")


def commit():
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HITO11, capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or "sin-git"
    except OSError:
        return "sin-git"


def medir(funcion):
    """Ejecuta funcion() y devuelve (resultado, error, ms)."""
    inicio = time.monotonic()
    try:
        return funcion(), None, (time.monotonic() - inicio) * 1000
    except Exception as exc:  # noqa: BLE001
        return None, exc, (time.monotonic() - inicio) * 1000


# ----------------------------------------------------------------------------- modo tcp

def probar_tcp(host, puerto, timeout):
    try:
        with socket.create_connection((host, puerto), timeout=timeout):
            return "OK", "conexion TCP establecida (hay un listener; todavia no se sabe si es el producto correcto)"
    except socket.gaierror as exc:
        return "FALLA", f"host no resuelto: {exc}"
    except (socket.timeout, TimeoutError):
        return "FALLA", f"timeout: sin respuesta en {timeout} s (firewall, ruta o servicio congelado)"
    except ConnectionRefusedError:
        return "FALLA", "connection refused: el host responde pero no hay nadie escuchando en ese puerto"
    except OSError as exc:
        return "FALLA", f"error de red: {exc}"


def modo_tcp(deps, timeout):
    reg = Registro("pruebas de configuracion, DNS y TCP")
    for nombre, (host, puerto, variables) in deps.items():
        if not host:
            reg.agregar(nombre, "configuracion", "FALLA", f"falta configurar {variables}")
            continue
        reg.agregar(nombre, "configuracion", "OK", f"{host}:{puerto} (variables: {variables})")
        try:
            ip = socket.gethostbyname(host)
            reg.agregar(nombre, "dns", "OK", f"{host} -> {ip}")
        except socket.gaierror as exc:
            reg.agregar(nombre, "dns", "FALLA", f"{host} no resuelve: {exc}")
            continue
        (resultado, detalle), _, ms = medir(lambda: probar_tcp(host, puerto, timeout))
        reg.agregar(nombre, "tcp", resultado, f"{host}:{puerto} -> {detalle}", ms)

    reg.escribir()
    reg.escribir("Contrastes (errores provocados a proposito):")
    resultado, detalle = probar_tcp("mongodb", 27017, timeout)
    reg.agregar("contraste", "dns", "OK" if "no resuelto" in detalle else "FALLA",
                f"nombre de servicio 'mongodb' desde la notebook -> {detalle} (ese nombre solo existe dentro de la red de Docker)")
    host, puerto, _ = deps["mongodb"]
    reg.agregar("contraste", "protocolo", *puerto_equivocado(host, puerto, timeout))
    reg.guardar("resultados_tcp")


def puerto_equivocado(host, puerto, timeout):
    """Mandar un PING de Redis al puerto de Mongo: el TCP conecta pero el protocolo no es el esperado."""
    try:
        with socket.create_connection((host, puerto), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall(b"PING\r\n")
            try:
                respuesta = s.recv(64)
                return "OK", f"PING de Redis al puerto de Mongo: TCP OK, respuesta {respuesta!r}: no es Redis"
            except (socket.timeout, TimeoutError):
                return "OK", "PING de Redis al puerto de Mongo: TCP OK pero no contesta (espera un mensaje de Mongo). Puerto abierto != protocolo correcto"
    except OSError as exc:
        return "SKIP", f"Mongo no esta arriba, no se puede mostrar el caso ({exc})"


# ----------------------------------------------------------------------------- modo nativos

class Cadena:
    """Ejecuta las capas en orden. Si una falla, las siguientes quedan NO_EJECUTADA."""

    def __init__(self, reg, dep):
        self.reg, self.dep, self.cortada = reg, dep, None

    def paso(self, capa, funcion):
        if self.cortada:
            self.reg.agregar(self.dep, capa, "NO_EJECUTADA", f"fallo la capa '{self.cortada}'")
            return
        valor, error, ms = medir(funcion)
        if error is not None:
            self.reg.agregar(self.dep, capa, "FALLA", f"{type(error).__name__}: {str(error)[:200]}", ms)
            self.cortada = capa
        elif isinstance(valor, tuple):  # (resultado, detalle) explicito, p.ej. N/A
            self.reg.agregar(self.dep, capa, valor[0], valor[1], ms)
        else:
            self.reg.agregar(self.dep, capa, "OK", valor, ms)


def nativo_mongodb(reg, t):
    from pymongo import MongoClient
    c = Cadena(reg, "mongodb")
    uri = env("MONGO_URI")
    base = urlparse(uri)
    sin_credenciales = MongoClient(host=base.hostname, port=base.port or 27017, serverSelectionTimeoutMS=t * 1000)
    cliente = MongoClient(uri, serverSelectionTimeoutMS=t * 1000)
    db = cliente[env("MONGO_DB", "fixture2030")]
    c.paso("protocolo", lambda: f"hello sin credenciales -> maxWireVersion={sin_credenciales.admin.command('hello')['maxWireVersion']}")
    c.paso("autenticacion", lambda: "usuario autenticado: " + str(cliente.admin.command("connectionStatus")["authInfo"]["authenticatedUsers"]))
    c.paso("contexto", lambda: f"database {db.name}, colecciones: {sorted(db.list_collection_names())}")
    c.paso("lectura", lambda: f"equipos.find_one(_id='ARG') -> {db.equipos.find_one({'_id': 'ARG'}, {'nombre': 1})}")
    c.paso("contraste", lambda: f"documento inexistente (ZZZ) -> {db.equipos.find_one({'_id': 'ZZZ'})} (ausencia, no error)")
    c.paso("contraste", lambda: f"database inexistente -> {cliente['no_existe'].list_collection_names()} (Mongo no da error: crea las bases al escribir)")


def nativo_neo4j(reg, t):
    import httpx
    from neo4j import GraphDatabase
    c = Cadena(reg, "neo4j")
    driver = GraphDatabase.driver(env("NEO4J_URI"), auth=(env("NEO4J_USER"), env("NEO4J_PASSWORD")), connection_timeout=t)
    try:
        c.paso("protocolo", lambda: (driver.verify_connectivity(), "Bolt responde")[1])
        c.paso("autenticacion", lambda: f"verify_authentication() = {driver.verify_authentication()}")
        c.paso("autorizacion", lambda: ("N/A", "Neo4j Community no tiene roles: cualquier usuario autenticado accede a todo"))

        def leer(cypher, **params):
            with driver.session(database="neo4j") as s:
                return s.run(cypher, **params).single()[0]
        c.paso("contexto", lambda: f"database 'neo4j': {leer('MATCH (p:Partido) RETURN count(p)')} partidos")
        c.paso("lectura", lambda: f"Partido F2030-006 -> {leer('MATCH (p:Partido {codigo:$c}) RETURN p.codigo', c='F2030-006')}")
        c.paso("contraste", lambda: f"partido inexistente F2030-999 -> {leer('MATCH (p:Partido {codigo:$c}) RETURN count(p)', c='F2030-999')} nodos")
        c.paso("contraste", lambda: f"eventos de F2030-001 (existe, sin eventos) -> "
                                    f"{leer('MATCH (:Partido {codigo:$c})<-[:OCURRE_EN]-(e:Evento) RETURN count(e)', c='F2030-001')} (vacio valido)")
    finally:
        driver.close()
    http = Cadena(reg, "neo4j-http")
    url = env("NEO4J_HTTP_URL", "http://localhost:7474")
    http.paso("protocolo", lambda: f"GET {url} -> HTTP {httpx.get(url, timeout=t).status_code} (Browser; la API no usa este puerto)")


def nativo_cassandra(reg, t):
    import logging
    from cassandra.cluster import Cluster
    logging.getLogger("cassandra").setLevel(logging.ERROR)
    c = Cadena(reg, "cassandra")
    ks = env("CASSANDRA_KEYSPACE", "fixture2030")
    cluster = Cluster(env("CASSANDRA_HOSTS", "localhost").split(","), port=int(env("CASSANDRA_PORT", "9042")), connect_timeout=t)
    sesion = {}
    try:
        def conectar():
            sesion["s"] = cluster.connect()
            return "sesion CQL abierta, Cassandra " + sesion["s"].execute("SELECT release_version FROM system.local").one()[0]
        c.paso("protocolo", conectar)
        c.paso("autenticacion", lambda: ("N/A", "sin autenticacion en el laboratorio (AllowAllAuthenticator, igual que el Hito 6)"))
        c.paso("contexto", lambda: f"keyspace {ks}, tablas: " + str([r[0] for r in sesion["s"].execute(
            "SELECT table_name FROM system_schema.tables WHERE keyspace_name = %s", (ks,))]))
        def leer_particion():
            filas = sesion["s"].execute(
                f"SELECT creado_en FROM {ks}.comentarios_por_bloque WHERE partido_id = %s AND bloque_horario = %s LIMIT 5",
                ("F2030-006", "203006181800"))
            return f"{len(list(filas))} comentarios de la particion (F2030-006, 203006181800), LIMIT 5"
        c.paso("lectura", leer_particion)

        def consulta_invalida():
            try:
                sesion["s"].execute(f"SELECT * FROM {ks}.comentarios_por_bloque WHERE partido_id = 'F2030-006'")
                return "sin error (inesperado)"
            except Exception as exc:  # noqa: BLE001
                return f"particion incompleta -> {type(exc).__name__} inmediato (no es un timeout)"
        c.paso("contraste", consulta_invalida)

        def keyspace_inexistente():
            try:
                cluster.connect("no_existe")
                return "sin error (inesperado)"
            except Exception as exc:  # noqa: BLE001
                return f"keyspace inexistente -> {type(exc).__name__}: {str(exc)[:90]}"
        c.paso("contraste", keyspace_inexistente)
    finally:
        cluster.shutdown()


def nativo_redis(reg, t):
    import redis
    c = Cadena(reg, "redis")
    r = redis.Redis(host=env("REDIS_HOST", "localhost"), port=int(env("REDIS_PORT", "6379")), db=int(env("REDIS_DB", "0")),
                    socket_connect_timeout=t, socket_timeout=t, decode_responses=True)
    c.paso("protocolo", lambda: f"PING -> {r.ping()}")
    c.paso("autenticacion", lambda: ("N/A", "sin requirepass en el laboratorio (igual que el Hito 7)"))
    c.paso("contexto", lambda: f"db {env('REDIS_DB', '0')}, maxmemory-policy={r.config_get('maxmemory-policy')['maxmemory-policy']}")
    c.paso("lectura", lambda: f"sesion user-00001: EXISTS={r.exists('fixture2030:sesion:user-00001')}, TTL={r.ttl('fixture2030:sesion:user-00001')} s")
    c.paso("contraste", lambda: f"clave ausente -> TTL={r.ttl('fixture2030:sesion:no-existe')} "
                                "(-2: no existe; una clave expirada se ve igual, Redis la borra al vencer)")


def nativo_influxdb(reg, t):
    import httpx
    c = Cadena(reg, "influxdb")
    url, db = env("INFLUX_URL", "http://localhost:8181"), env("INFLUX_DATABASE", "fixture2030_series")
    token = {"Authorization": f"Bearer {env('INFLUX_TOKEN')}"}

    def sql(consulta, base=db, headers=token):
        return httpx.post(f"{url}/api/v3/query_sql", headers=headers, json={"db": base, "q": consulta, "format": "json"}, timeout=t)

    c.paso("protocolo", lambda: f"GET /health sin token -> HTTP {httpx.get(url + '/health', timeout=t).status_code} (401 = vivo y protegido)")
    if not env("INFLUX_TOKEN"):
        reg.agregar("influxdb", "autenticacion", "SKIP", "INFLUX_TOKEN vacio en el .env del Hito 10")
        return
    c.paso("autenticacion", lambda: f"GET /health con token -> HTTP {httpx.get(url + '/health', headers=token, timeout=t).status_code}")
    c.paso("contexto", lambda: f"database {db}: SELECT 1 -> HTTP {sql('SELECT 1').status_code}")
    def leer_ventana():
        consulta = ("SELECT time FROM estadisticas WHERE partido_id = 'F2030-006' AND equipo_id = 'ARG' "
                    "AND time >= '2030-06-18T18:00:00Z' AND time < '2030-06-18T18:05:00Z' LIMIT 10")
        return f"{len(sql(consulta).json())} puntos en una ventana de 5 minutos (LIMIT 10)"
    c.paso("lectura", leer_ventana)
    c.paso("contraste", lambda: f"database inexistente -> HTTP {sql('SELECT 1', base='no_existe').status_code}")
    c.paso("contraste", lambda: f"token invalido -> HTTP {httpx.get(url + '/health', headers={'Authorization': 'Bearer malo'}, timeout=t).status_code}")


def nativo_iris(reg, t):
    import httpx
    import iris
    c = Cadena(reg, "iris")
    conexion = {}

    def conectar():
        conexion["c"] = iris.connect(hostname=env("IRIS_HOST"), port=int(env("IRIS_PORT", "1972")), namespace=env("IRIS_NAMESPACE", "USER"),
                                     username=env("IRIS_USER"), password=env("IRIS_PASSWORD"), timeout=int(t), sharedmemory=False)
        conexion["i"] = iris.createIRIS(conexion["c"])
        return "Superserver: conexion y login OK (el SDK no separa handshake y login)"
    c.paso("autenticacion", conectar)
    c.paso("contexto", lambda: f"namespace {env('IRIS_NAMESPACE', 'USER')}, clase Fixture.Partido compilada = "
                               f"{conexion['i'].classMethodValue('%Dictionary.CompiledClass', '%ExistsId', 'Fixture.Partido')}")
    c.paso("lectura", lambda: "F2030-006 -> " + conexion["i"].classMethodValue("Fixture.ApiSupport", "ObtenerPartidoDetalle", "F2030-006")[:110])
    c.paso("contraste", lambda: "F2030-999 -> " + conexion["i"].classMethodValue("Fixture.ApiSupport", "ObtenerPartidoDetalle", "F2030-999"))
    if "c" in conexion:
        conexion["c"].close()
    portal = Cadena(reg, "iris-portal")
    url = env("IRIS_PORTAL_URL", "http://localhost:52773")
    portal.paso("protocolo", lambda: f"GET /csp/sys/UtilHome.csp -> HTTP {httpx.get(url + '/csp/sys/UtilHome.csp', timeout=t).status_code} (portal; la API usa el 1972)")


# Cliente de linea de comandos oficial de cada producto, dentro de su contenedor.
# Sirve para el caso "el cliente nativo funciona pero la API falla". Ojo: el origen
# de esta prueba es el contenedor de la base, no la notebook donde corre la API.
CLIS = {
    "mongodb": ("mongosh", "h10-mongodb", ["sh", "-c", 'mongosh --quiet -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" '
                                '--authenticationDatabase admin fixture2030 --eval "db.equipos.countDocuments({})"']),
    "neo4j": ("cypher-shell", "h10-neo4j", ["sh", "-c", 'cypher-shell -u neo4j -p "${NEO4J_AUTH#neo4j/}" "MATCH (p:Partido) RETURN count(p)"']),
    "cassandra": ("cqlsh", "h10-cassandra", ["cqlsh", "-e", "SELECT count(*) FROM fixture2030.comentarios_por_bloque WHERE partido_id='F2030-006' AND bloque_horario='203006181800'"]),
    "redis": ("redis-cli", "h10-redis", ["redis-cli", "TTL", "fixture2030:sesion:user-00001"]),
    "iris": ("iris session", "h10-iris", ["sh", "-c", "echo 'Write ##class(Fixture.Partido).CodigoIdxExists(\"F2030-006\"),! Halt' | iris session IRIS -U USER"]),
}


def probar_cli(reg, dep):
    if dep not in CLIS:
        return
    cliente, contenedor, comando = CLIS[dep]
    if not shutil.which("docker"):
        reg.agregar(dep, "cliente CLI", "SKIP", "docker no esta disponible en este entorno (falta la herramienta, no es una falla del producto)")
        return
    r, error, ms = medir(lambda: subprocess.run(["docker", "exec", contenedor, *comando], capture_output=True, text=True, timeout=30))
    if error is not None or r.returncode != 0:
        detalle = str(error) if error else (r.stderr or r.stdout).strip()[-150:]
        reg.agregar(dep, "cliente CLI", "FALLA", f"{cliente} en {contenedor}: {detalle}", ms)
    else:
        salida = " | ".join(l.strip() for l in r.stdout.splitlines() if l.strip() and "USER>" not in l and "Node:" not in l)
        reg.agregar(dep, "cliente CLI", "OK", f"{cliente} en {contenedor} -> {salida[-80:]}", ms)


def modo_nativos(productos, timeout):
    reg = Registro("pruebas con el cliente/driver de cada producto")
    pruebas = {"mongodb": nativo_mongodb, "neo4j": nativo_neo4j, "cassandra": nativo_cassandra,
               "redis": nativo_redis, "influxdb": nativo_influxdb, "iris": nativo_iris}
    for dep, funcion in pruebas.items():
        if productos and dep not in productos:
            continue
        reg.escribir(f"\n== {dep}")
        try:
            funcion(reg, timeout)
        except ImportError as exc:
            reg.agregar(dep, "driver", "SKIP", f"falta el driver de Python ({exc}); usar el venv del Hito 10")
        except Exception as exc:  # noqa: BLE001 - p.ej. el driver falla al crear el cliente
            reg.agregar(dep, "conexion", "FALLA", f"{type(exc).__name__}: {str(exc)[:200]}")
        probar_cli(reg, dep)
    reg.guardar("resultados_clientes")


# ----------------------------------------------------------------------------- modo api

VENTANA = "equipo_id=ARG&desde=2030-06-18T18:00:00Z&hasta=2030-06-18T18:05:00Z"
RUTAS = [
    # (metodo, ruta, status esperado, dependencia, que se prueba)
    ("GET", "/salud/vivo", 200, "-", "liveness"),
    ("GET", "/salud/listo", 200, "todas", "readiness"),
    ("GET", "/equipos/ARG", 200, "mongodb", "exitosa"),
    ("GET", "/equipos/ZZZ", 404, "mongodb", "recurso inexistente"),
    ("GET", "/equipos?confederacion=XXX", 400, "mongodb", "validacion (no consulta la base)"),
    ("GET", "/partidos/F2030-006", 200, "neo4j", "exitosa"),
    ("GET", "/partidos/F2030-001/eventos", 200, "neo4j", "vacia valida (items=[])"),
    ("GET", "/partidos/F2030-999", 404, "neo4j", "recurso inexistente"),
    ("GET", "/partidos/F2030-006/comentarios?bloque_horario=203006181800", 200, "cassandra", "exitosa"),
    ("GET", "/partidos/F2030-006/comentarios?bloque_horario=mal", 400, "cassandra", "validacion"),
    ("GET", "/sesiones/user-00001", 200, "redis", "exitosa"),
    ("GET", "/sesiones/no-existe", 404, "redis", "sesion ausente o expirada"),
    ("GET", f"/partidos/F2030-006/estadisticas?{VENTANA}", 200, "influxdb", "exitosa"),
    ("GET", "/partidos/F2030-006/estadisticas?equipo_id=ARG&desde=2030-06-19T18:00:00Z&hasta=2030-06-19T18:05:00Z", 200, "influxdb", "vacia valida"),
    ("GET", "/partidos/F2030-006/entidad-compleja", 200, "iris", "exitosa (mismo codigo que las otras bases)"),
    ("GET", "/partidos/F2030-999/entidad-compleja", 404, "iris", "recurso inexistente"),
    ("GET", "/partidos/M001/entidad-compleja", 400, "iris", "codigo viejo de IRIS: ya no se acepta"),
]


def modo_api(productos, timeout):
    import httpx
    reg = Registro("pruebas de la API (cliente HTTP -> API -> adaptador -> base)")
    base = env("API_URL", "http://localhost:8000")
    try:
        httpx.get(base + "/salud/vivo", timeout=timeout)
    except httpx.HTTPError as exc:
        reg.agregar("api", "api", "FALLA", f"API no alcanzable en {base}: {exc}. Levantarla con bash scripts/iniciar_api.sh (Hito 10)")
        reg.guardar("resultados_api")
        return
    log = HITO10 / "api.log"
    for metodo, ruta, esperado, dep, que in RUTAS:
        if productos and dep not in productos and dep not in ("-", "todas"):
            continue
        r, error, ms = medir(lambda: httpx.request(metodo, base + ruta, timeout=timeout + 10))
        if error is not None:
            reg.agregar(dep, "api", "FALLA", f"{metodo} {ruta}: {error}", ms)
            continue
        request_id = r.headers.get("X-Request-Id", "-")
        cuerpo = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        resumen = cuerpo.get("error", {}).get("tipo") if isinstance(cuerpo, dict) and "error" in cuerpo else (
            f"items={len(cuerpo['items'])}" if isinstance(cuerpo, dict) and "items" in cuerpo else "ok")
        resultado = "OK" if r.status_code == esperado else "FALLA"
        reg.agregar(dep, "api", resultado, f"{metodo} {ruta} -> HTTP {r.status_code} (esperado {esperado}, {que}) | {resumen} | request_id={request_id}", ms)
        if log.exists():
            for linea in log.read_text(encoding="utf-8", errors="replace").splitlines():
                if request_id in linea:
                    reg.escribir("      log: " + linea.split("fixture2030.api ")[-1])
    if not log.exists():
        reg.escribir("(no se encontro api.log del Hito 10: iniciar la API con scripts/iniciar_api.sh para tener los logs asociados)")
    reg.guardar("resultados_api")


# ----------------------------------------------------------------------------- matriz

def matriz():
    """Arma docs/evidencia/matriz.md con el estado de cada dependencia a partir de los .json guardados."""
    filas = []
    for archivo in ("resultados_tcp", "resultados_clientes", "resultados_api"):
        ruta = EVIDENCIA / f"{archivo}.json"
        if ruta.exists():
            filas += json.loads(ruta.read_text(encoding="utf-8"))
    lineas = [f"# Matriz de conectividad (generada {datetime.now().astimezone().isoformat(timespec='seconds')}, commit {commit()})", "",
              "| Dependencia | Estado | TCP | Cliente/driver | API | Diagnostico |", "|---|---|---|---|---|---|"]
    for dep in dependencias():
        propias = [f for f in filas if f["dependencia"] == dep and f["capa"] != "contraste"]
        tcp = [f for f in propias if f["capa"] in ("configuracion", "dns", "tcp")]
        nat = [f for f in propias if f["capa"] not in ("configuracion", "dns", "tcp", "api")]
        api = [f for f in propias if f["capa"] == "api"]
        resumen = lambda fs: "-" if not fs else ("FALLA" if any(f["resultado"] == "FALLA" for f in fs) else "OK")  # noqa: E731
        fallas = [f for f in propias if f["resultado"] in ("FALLA", "NO_EJECUTADA")]
        if not propias:
            estado, diag = "no probado", "no se ejecuto ninguna prueba"
        elif fallas and resumen(nat) != "OK":
            estado, diag = "no disponible", f"falla en '{fallas[0]['capa']}': {fallas[0]['detalle'][:90]}"
        elif fallas:
            estado, diag = "degradado", f"el producto responde pero falla la API: {fallas[0]['detalle'][:90]}"
        elif nat or api:
            estado, diag = "disponible", "todas las pruebas ejecutadas dieron OK"
        else:
            estado, diag = "desconocido", "solo se probo TCP: no alcanza para decir que funciona"
        lineas.append(f"| {dep} | {estado} | {resumen(tcp)} | {resumen(nat)} | {resumen(api)} | {diag.replace('|', '/')} |")
    (EVIDENCIA / "matriz.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas[2:]))
    print("-> docs/evidencia/matriz.md")


# -----------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Evaluacion de conectividad del Hito 11")
    p.add_argument("--modo", default="completo", choices=["completo", "tcp", "nativos", "api"])
    p.add_argument("--producto", default="", help="mongodb, neo4j, cassandra, redis, influxdb o iris")
    args = p.parse_args()

    cargar_env(HITO11 / "config" / "local.env")
    cargar_env(HITO10 / ".env")
    timeout = float(env("TIMEOUT_S", "3"))
    productos = [x.strip() for x in args.producto.split(",") if x.strip()]
    deps = {k: v for k, v in dependencias().items() if not productos or k.split("-")[0] in productos}

    if args.modo in ("completo", "tcp"):
        modo_tcp(deps, timeout)
    if args.modo in ("completo", "nativos"):
        modo_nativos(productos, timeout)
    if args.modo in ("completo", "api"):
        modo_api(productos, timeout)
    matriz()


if __name__ == "__main__":
    main()
