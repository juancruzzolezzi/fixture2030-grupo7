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
SECRETOS = ("MONGO_PASSWORD", "NEO4J_PASSWORD", "IRIS_PASSWORD", "INFLUX_TOKEN")


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
    neo = urlparse(env("NEO4J_URI", "bolt://127.0.0.1:7687"))
    neo_http = urlparse(env("NEO4J_HTTP_URL", "http://127.0.0.1:7474"))
    influx = urlparse(env("INFLUX_URL", "http://127.0.0.1:8181"))
    iris_portal = urlparse(env("IRIS_PORTAL_URL", "http://127.0.0.1:52773"))
    return {
        "mongodb": (env("MONGO_HOST", "127.0.0.1"), int(env("MONGO_PORT", "27017")), "MONGO_HOST, MONGO_PORT, MONGO_USER, MONGO_PASSWORD"),
        "neo4j": (neo.hostname, neo.port or 7687, "NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD"),
        "neo4j-http": (neo_http.hostname, neo_http.port or 7474, "NEO4J_HTTP_URL"),
        "cassandra": (env("CASSANDRA_HOSTS", "127.0.0.1").split(",")[0], int(env("CASSANDRA_PORT", "9042")), "CASSANDRA_HOSTS, CASSANDRA_KEYSPACE"),
        "redis": (env("REDIS_HOST", "127.0.0.1"), int(env("REDIS_PORT", "6379")), "REDIS_HOST, REDIS_PORT"),
        "influxdb": (influx.hostname, influx.port or 8181, "INFLUX_URL, INFLUX_DATABASE, INFLUX_TOKEN"),
        "iris": (env("IRIS_HOST", "127.0.0.1"), int(env("IRIS_PORT", "1972")), "IRIS_HOST, IRIS_NAMESPACE, IRIS_USER, IRIS_PASSWORD"),
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


class PruebaFallida(Exception):
    """La operacion respondio, pero no lo que se esperaba (status, contenido, dato ausente)."""


def exigir(condicion, mensaje):
    """Una prueba solo es OK si el resultado es el esperado; si no, queda FALLA."""
    if not condicion:
        raise PruebaFallida(mensaje)


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
    if "mongodb" in deps:  # con --producto redis no se toca Mongo
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
            detalle = str(error) if isinstance(error, PruebaFallida) else f"{type(error).__name__}: {str(error)[:200]}"
            self.reg.agregar(self.dep, capa, "FALLA", detalle, ms)
            if capa != "contraste":  # un contraste fallido no invalida las capas
                self.cortada = capa
        elif isinstance(valor, tuple):  # (resultado, detalle) explicito, p.ej. N/A
            self.reg.agregar(self.dep, capa, valor[0], valor[1], ms)
        else:
            self.reg.agregar(self.dep, capa, "OK", valor, ms)


def nativo_mongodb(reg, t):
    from urllib.parse import quote_plus
    from pymongo import MongoClient
    c = Cadena(reg, "mongodb")
    host, puerto = env("MONGO_HOST", "127.0.0.1"), int(env("MONGO_PORT", "27017"))
    sin_credenciales = MongoClient(host=host, port=puerto, serverSelectionTimeoutMS=t * 1000)
    cliente = MongoClient(f"mongodb://{quote_plus(env('MONGO_USER'))}:{quote_plus(env('MONGO_PASSWORD'))}@{host}:{puerto}/?authSource=admin",
                          serverSelectionTimeoutMS=t * 1000)
    db = cliente[env("MONGO_DB", "fixture2030")]
    c.paso("protocolo", lambda: f"hello sin credenciales -> maxWireVersion={sin_credenciales.admin.command('hello')['maxWireVersion']}")

    def autenticacion():
        usuarios = cliente.admin.command("connectionStatus")["authInfo"]["authenticatedUsers"]
        exigir(usuarios, "connectionStatus no tiene usuarios autenticados")
        return f"usuario autenticado: {usuarios[0]['user']}"
    c.paso("autenticacion", autenticacion)

    def contexto():
        colecciones = sorted(db.list_collection_names())
        exigir({"equipos", "jugadores"} <= set(colecciones),
               f"en la base {db.name} faltan equipos/jugadores (hay: {colecciones}); Mongo no da error si la base no existe")
        return f"database {db.name}, colecciones: {colecciones}"
    c.paso("contexto", contexto)

    def lectura():
        doc = db.equipos.find_one({"_id": "ARG"}, {"nombre": 1})
        exigir(doc is not None, "equipos.find_one(_id='ARG') no devolvio nada (falta sembrar?)")
        return f"equipos.find_one(_id='ARG') -> {doc}"
    c.paso("lectura", lectura)

    def doc_inexistente():
        doc = db.equipos.find_one({"_id": "ZZZ"})
        exigir(doc is None, "se esperaba None para ZZZ")
        return "documento inexistente (ZZZ) -> None (ausencia, no error)"
    c.paso("contraste", doc_inexistente)

    def base_inexistente():
        colecciones = cliente["no_existe"].list_collection_names()
        exigir(colecciones == [], f"se esperaba [] y vino {colecciones}")
        return "database inexistente -> [] sin error (Mongo crea las bases recien al escribir)"
    c.paso("contraste", base_inexistente)


def nativo_neo4j(reg, t):
    import httpx
    from neo4j import GraphDatabase
    c = Cadena(reg, "neo4j")
    driver = GraphDatabase.driver(env("NEO4J_URI"), auth=(env("NEO4J_USER"), env("NEO4J_PASSWORD")), connection_timeout=t)
    try:
        c.paso("protocolo", lambda: (driver.verify_connectivity(), "Bolt responde")[1])

        def autenticacion():
            exigir(driver.verify_authentication(), "verify_authentication() devolvio False")
            return "verify_authentication() = True"
        c.paso("autenticacion", autenticacion)
        c.paso("autorizacion", lambda: ("N/A", "Neo4j Community no tiene roles: cualquier usuario autenticado accede a todo"))

        def leer(cypher, **params):
            with driver.session(database="neo4j") as s:
                fila = s.run(cypher, **params).single()
                return None if fila is None else fila[0]

        def contexto():
            n = leer("MATCH (p:Partido) RETURN count(p)")
            exigir(n and n > 0, "la base 'neo4j' no tiene partidos (falta sembrar?)")
            return f"database 'neo4j': {n} partidos"
        c.paso("contexto", contexto)

        def lectura():
            codigo = leer("MATCH (p:Partido {codigo:$c}) RETURN p.codigo", c="F2030-006")
            exigir(codigo == "F2030-006", "no se encontro el partido F2030-006")
            return f"Partido F2030-006 -> {codigo}"
        c.paso("lectura", lectura)

        def inexistente():
            n = leer("MATCH (p:Partido {codigo:$c}) RETURN count(p)", c="F2030-999")
            exigir(n == 0, f"se esperaban 0 nodos y hubo {n}")
            return "partido inexistente F2030-999 -> 0 nodos"
        c.paso("contraste", inexistente)

        def vacio_valido():
            n = leer("MATCH (:Partido {codigo:$c})<-[:OCURRE_EN]-(e:Evento) RETURN count(e)", c="F2030-001")
            exigir(n == 0, f"se esperaban 0 eventos y hubo {n}")
            return "eventos de F2030-001 (existe, sin eventos) -> 0 (vacio valido)"
        c.paso("contraste", vacio_valido)
    finally:
        driver.close()
    http = Cadena(reg, "neo4j-http")
    url = env("NEO4J_HTTP_URL", "http://127.0.0.1:7474")

    def browser():
        r = httpx.get(url, timeout=t)
        exigir(r.status_code == 200, f"GET {url} -> HTTP {r.status_code}")
        return f"GET {url} -> HTTP 200 (Browser; la API no usa este puerto)"
    http.paso("protocolo", browser)


def nativo_cassandra(reg, t):
    import logging
    from cassandra.cluster import Cluster
    logging.getLogger("cassandra").setLevel(logging.ERROR)
    c = Cadena(reg, "cassandra")
    ks = env("CASSANDRA_KEYSPACE", "fixture2030")
    cluster = Cluster(env("CASSANDRA_HOSTS", "127.0.0.1").split(","), port=int(env("CASSANDRA_PORT", "9042")), connect_timeout=t)
    sesion = {}
    try:
        def conectar():
            sesion["s"] = cluster.connect()
            return "sesion CQL abierta, Cassandra " + sesion["s"].execute("SELECT release_version FROM system.local").one()[0]
        c.paso("protocolo", conectar)
        c.paso("autenticacion", lambda: ("N/A", "sin autenticacion en el laboratorio (AllowAllAuthenticator, igual que el Hito 6)"))

        def contexto():
            tablas = [r[0] for r in sesion["s"].execute("SELECT table_name FROM system_schema.tables WHERE keyspace_name = %s", (ks,))]
            exigir("comentarios_por_bloque" in tablas, f"el keyspace {ks} no existe o no tiene comentarios_por_bloque")
            return f"keyspace {ks}, tablas: {tablas}"
        c.paso("contexto", contexto)

        def leer_particion():
            filas = list(sesion["s"].execute(
                f"SELECT creado_en FROM {ks}.comentarios_por_bloque WHERE partido_id = %s AND bloque_horario = %s LIMIT 5",
                ("F2030-006", "203006181800")))
            exigir(filas, "la particion (F2030-006, 203006181800) esta vacia (falta sembrar?)")
            return f"{len(filas)} comentarios de la particion (F2030-006, 203006181800), LIMIT 5"
        c.paso("lectura", leer_particion)

        def consulta_invalida():
            try:
                sesion["s"].execute(f"SELECT * FROM {ks}.comentarios_por_bloque WHERE partido_id = 'F2030-006'")
            except Exception as exc:  # noqa: BLE001
                return f"particion incompleta -> {type(exc).__name__} inmediato (no es un timeout)"
            raise PruebaFallida("la consulta sin bloque_horario no dio error")
        c.paso("contraste", consulta_invalida)

        def keyspace_inexistente():
            try:
                cluster.connect("no_existe")
            except Exception as exc:  # noqa: BLE001
                return f"keyspace inexistente -> {type(exc).__name__}: {str(exc)[:90]}"
            raise PruebaFallida("conectar a un keyspace inexistente no dio error")
        c.paso("contraste", keyspace_inexistente)
    finally:
        cluster.shutdown()


def nativo_redis(reg, t):
    import redis
    c = Cadena(reg, "redis")
    r = redis.Redis(host=env("REDIS_HOST", "127.0.0.1"), port=int(env("REDIS_PORT", "6379")), db=int(env("REDIS_DB", "0")),
                    socket_connect_timeout=t, socket_timeout=t, decode_responses=True)

    def protocolo():
        exigir(r.ping(), "PING no devolvio PONG")
        return "PING -> PONG"
    c.paso("protocolo", protocolo)
    c.paso("autenticacion", lambda: ("N/A", "sin requirepass en el laboratorio (igual que el Hito 7)"))
    c.paso("contexto", lambda: f"db {env('REDIS_DB', '0')}, maxmemory-policy={r.config_get('maxmemory-policy')['maxmemory-policy']}")

    def lectura():
        clave = "fixture2030:sesion:user-00001"
        exigir(r.exists(clave), f"no existe {clave} (expiro o falta sembrar)")
        return f"sesion user-00001: existe, TTL={r.ttl(clave)} s"
    c.paso("lectura", lectura)

    def ausente():
        ttl = r.ttl("fixture2030:sesion:no-existe")
        exigir(ttl == -2, f"se esperaba TTL -2 y vino {ttl}")
        return "clave ausente -> TTL=-2 (no existe; una clave expirada se ve igual, Redis la borra al vencer)"
    c.paso("contraste", ausente)


def nativo_influxdb(reg, t):
    import httpx
    c = Cadena(reg, "influxdb")
    url, db = env("INFLUX_URL", "http://127.0.0.1:8181"), env("INFLUX_DATABASE", "fixture2030_series")
    token = {"Authorization": f"Bearer {env('INFLUX_TOKEN')}"}

    def sql(consulta, base=db):
        return httpx.post(f"{url}/api/v3/query_sql", headers=token, json={"db": base, "q": consulta, "format": "json"}, timeout=t)

    def protocolo():
        codigo = httpx.get(url + "/health", timeout=t).status_code
        exigir(codigo in (200, 401), f"GET /health sin token -> HTTP {codigo}")
        return f"GET /health sin token -> HTTP {codigo} (401 = vivo y protegido)"
    c.paso("protocolo", protocolo)
    if not env("INFLUX_TOKEN"):
        reg.agregar("influxdb", "autenticacion", "SKIP", "INFLUX_TOKEN vacio en el .env del Hito 10")
        return

    def autenticacion():
        codigo = httpx.get(url + "/health", headers=token, timeout=t).status_code
        exigir(codigo == 200, f"GET /health con token -> HTTP {codigo}: el token fue rechazado")
        return "GET /health con token -> HTTP 200"
    c.paso("autenticacion", autenticacion)

    def contexto():
        r = sql("SELECT 1")
        exigir(r.status_code == 200, f"SELECT 1 en {db} -> HTTP {r.status_code}: {r.text[:80]}")
        return f"database {db}: SELECT 1 -> HTTP 200"
    c.paso("contexto", contexto)

    def leer_ventana():
        r = sql("SELECT time FROM estadisticas WHERE partido_id = 'F2030-006' AND equipo_id = 'ARG' "
                "AND time >= '2030-06-18T18:00:00Z' AND time < '2030-06-18T18:05:00Z' LIMIT 10")
        exigir(r.status_code == 200, f"consulta -> HTTP {r.status_code}: {r.text[:80]}")
        puntos = r.json()
        exigir(isinstance(puntos, list) and puntos, f"la respuesta no trae puntos: {str(puntos)[:80]}")
        return f"{len(puntos)} puntos en una ventana de 5 minutos (LIMIT 10)"
    c.paso("lectura", leer_ventana)

    def db_inexistente():
        codigo = sql("SELECT 1", base="no_existe").status_code
        exigir(codigo == 404, f"se esperaba 404 y vino {codigo}")
        return "database inexistente -> HTTP 404"
    c.paso("contraste", db_inexistente)

    def token_invalido():
        codigo = httpx.get(url + "/health", headers={"Authorization": "Bearer malo"}, timeout=t).status_code
        exigir(codigo == 401, f"se esperaba 401 y vino {codigo}")
        return "token invalido -> HTTP 401"
    c.paso("contraste", token_invalido)


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

    def contexto():
        compilada = conexion["i"].classMethodValue("%Dictionary.CompiledClass", "%ExistsId", "Fixture.Partido")
        exigir(compilada, "la clase Fixture.Partido no esta compilada en el namespace")
        return f"namespace {env('IRIS_NAMESPACE', 'USER')}, clase Fixture.Partido compilada"
    c.paso("contexto", contexto)

    def lectura():
        datos = json.loads(conexion["i"].classMethodValue("Fixture.ApiSupport", "ObtenerPartidoDetalle", "F2030-006"))
        exigir(datos.get("encontrado"), "IRIS no tiene el partido F2030-006 (falta sembrar?)")
        return f"F2030-006 -> estado {datos['estado']}, {len(datos['eventos'])} evento(s)"
    c.paso("lectura", lectura)

    def inexistente():
        datos = json.loads(conexion["i"].classMethodValue("Fixture.ApiSupport", "ObtenerPartidoDetalle", "F2030-999"))
        exigir(not datos.get("encontrado"), "F2030-999 aparecio como encontrado")
        return "F2030-999 -> encontrado: false"
    c.paso("contraste", inexistente)
    if "c" in conexion:
        conexion["c"].close()
    portal = Cadena(reg, "iris-portal")
    url = env("IRIS_PORTAL_URL", "http://127.0.0.1:52773")

    def ver_portal():
        codigo = httpx.get(url + "/csp/sys/UtilHome.csp", timeout=t).status_code
        exigir(codigo == 200, f"portal -> HTTP {codigo}")
        return "GET /csp/sys/UtilHome.csp -> HTTP 200 (portal; la API usa el 1972)"
    portal.paso("protocolo", ver_portal)


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


# Que el comando termine bien no alcanza: el numero que devuelve tiene que ser el esperado.
def _enteros(texto):
    return [int(x) for x in re.findall(r"-?\d+", texto)]


VALIDAR_CLI = {
    "mongodb": lambda n: n and n[-1] > 0,      # cantidad de equipos
    "neo4j": lambda n: n and n[-1] > 0,        # cantidad de partidos
    "cassandra": lambda n: n and n[0] > 0,     # count(*) de la particion (despues viene "(1 rows)")
    "redis": lambda n: n and n[-1] > 0,        # TTL de la sesion (-2 = no existe)
    "iris": lambda n: n and n[-1] == 1,        # CodigoIdxExists("F2030-006")
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
        ok = VALIDAR_CLI[dep](_enteros(salida))
        reg.agregar(dep, "cliente CLI", "OK" if ok else "FALLA",
                    f"{cliente} en {contenedor} -> {salida[-80:]}" + ("" if ok else " (no es el valor esperado)"), ms)


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
    base = env("API_URL", "http://127.0.0.1:8000")
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
        try:
            cuerpo = r.json()
        except ValueError:
            cuerpo = {}
        resumen = cuerpo.get("error", {}).get("tipo") if isinstance(cuerpo, dict) and "error" in cuerpo else (
            f"items={len(cuerpo['items'])}" if isinstance(cuerpo, dict) and "items" in cuerpo else "ok")
        resultado = "OK" if r.status_code == esperado else "FALLA"
        if "vacia" in que and resumen != "items=0":
            resultado = "FALLA"  # se esperaba 200 con items=[]
        reg.agregar(dep, "api", resultado, f"{metodo} {ruta} -> HTTP {r.status_code} (esperado {esperado}, {que}) | {resumen} | request_id={request_id}", ms)
        if log.exists():
            for linea in log.read_text(encoding="utf-8", errors="replace").splitlines():
                if request_id in linea:
                    reg.escribir("      log: " + linea.split("fixture2030.api ")[-1])
    if not log.exists():
        reg.escribir("(no se encontro api.log del Hito 10: iniciar la API con scripts/iniciar_api.sh para tener los logs asociados)")
    reg.guardar("resultados_api")


# ----------------------------------------------------------------------------- matriz

def celda(filas):
    """Resume un grupo de pruebas. Solo dice OK si hubo al menos una prueba que dio OK
    y ninguna fallo; SKIP o N/A solos no cuentan como prueba valida."""
    resultados = {f["resultado"] for f in filas}
    if not filas:
        return "-"
    if resultados & {"FALLA", "NO_EJECUTADA"}:
        return "FALLA"
    if "OK" in resultados:
        return "OK" + (" (con SKIP)" if "SKIP" in resultados else "")
    return "SKIP" if "SKIP" in resultados else "N/A"


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
        fallas = [f for f in propias if f["resultado"] in ("FALLA", "NO_EJECUTADA")]
        hay_ok = any(f["resultado"] == "OK" for f in nat + api)
        if not propias:
            estado, diag = "no probado", "no se ejecuto ninguna prueba"
        elif fallas and celda(nat) == "FALLA" or (fallas and not api and not nat):
            estado, diag = "no disponible", f"falla en '{fallas[0]['capa']}': {fallas[0]['detalle'][:90]}"
        elif fallas:
            estado, diag = "degradado", f"falla en '{fallas[0]['capa']}': {fallas[0]['detalle'][:90]}"
        elif hay_ok:
            saltadas = [f for f in nat + api if f["resultado"] == "SKIP"]
            estado = "disponible"
            diag = "todas las pruebas ejecutadas dieron OK" + (f" ({len(saltadas)} prueba(s) SKIP, ver detalle)" if saltadas else "")
        elif any(f["resultado"] == "SKIP" for f in nat + api):
            estado, diag = "no probado", "las pruebas del cliente/driver quedaron en SKIP (falta herramienta o configuracion)"
        else:
            estado, diag = "desconocido", "solo se probo TCP: no alcanza para decir que funciona"
        lineas.append(f"| {dep} | {estado} | {celda(tcp)} | {celda(nat)} | {celda(api)} | {diag.replace('|', '/')} |")
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
    validos = {"mongodb", "neo4j", "cassandra", "redis", "influxdb", "iris"}
    if set(productos) - validos:
        p.error(f"producto desconocido: {sorted(set(productos) - validos)}. Validos: {sorted(validos)}")
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
