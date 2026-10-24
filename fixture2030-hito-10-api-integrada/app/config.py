# -*- coding: utf-8 -*-
"""
Configuracion de la API (Hito 10, Grupo 7).

Todo lo que es host/puerto/credencial sale de variables de entorno (RNF6).
Las passwords no tienen valor por defecto: si falta alguna en el .env, la
conexion falla y la API responde 503 (no se usa una password escrita en el codigo).
"""

import os
from dataclasses import dataclass
from urllib.parse import quote_plus


def _env(nombre: str, default: str) -> str:
    return os.environ.get(nombre, default)


def _mongo_uri() -> str:
    """La URI se arma en memoria con las partes del .env (asi no hay una URI con
    password escrita en ningun archivo)."""
    usuario = quote_plus(_env("MONGO_USER", ""))
    password = quote_plus(_env("MONGO_PASSWORD", ""))
    host, puerto = _env("MONGO_HOST", "127.0.0.1"), _env("MONGO_PORT", "27017")
    return f"mongodb://{usuario}:{password}@{host}:{puerto}/?authSource=admin"


@dataclass(frozen=True)
class MongoConfig:
    uri: str = _mongo_uri()
    db: str = _env("MONGO_DB", "fixture2030")
    timeout_ms: int = int(_env("MONGO_TIMEOUT_MS", "3000"))


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str = _env("NEO4J_URI", "bolt://127.0.0.1:7687")
    usuario: str = _env("NEO4J_USER", "neo4j")
    password: str = _env("NEO4J_PASSWORD", "")
    timeout_s: float = float(_env("NEO4J_TIMEOUT_S", "3"))


@dataclass(frozen=True)
class CassandraConfig:
    hosts: tuple = tuple(_env("CASSANDRA_HOSTS", "localhost").split(","))
    puerto: int = int(_env("CASSANDRA_PORT", "9042"))
    keyspace: str = _env("CASSANDRA_KEYSPACE", "fixture2030")
    timeout_s: float = float(_env("CASSANDRA_TIMEOUT_S", "3"))


@dataclass(frozen=True)
class RedisConfig:
    host: str = _env("REDIS_HOST", "localhost")
    puerto: int = int(_env("REDIS_PORT", "6379"))
    db: int = int(_env("REDIS_DB", "0"))
    timeout_s: float = float(_env("REDIS_TIMEOUT_S", "2"))


@dataclass(frozen=True)
class InfluxConfig:
    url: str = _env("INFLUX_URL", "http://localhost:8181")
    database: str = _env("INFLUX_DATABASE", "fixture2030_series")
    token: str = _env("INFLUX_TOKEN", "")  # sale de .influxdb3-token, nunca hardcodeado
    timeout_s: float = float(_env("INFLUX_TIMEOUT_S", "3"))
    reusar_cliente: bool = _env("INFLUX_REUSAR_CLIENTE", "1") == "1"  # Hito 12; 0 = como en el Hito 10


@dataclass(frozen=True)
class IrisConfig:
    hostname: str = _env("IRIS_HOST", "localhost")
    puerto: int = int(_env("IRIS_PORT", "1972"))
    namespace: str = _env("IRIS_NAMESPACE", "USER")
    usuario: str = _env("IRIS_USER", "_SYSTEM")
    password: str = _env("IRIS_PASSWORD", "")
    timeout_s: float = float(_env("IRIS_TIMEOUT_S", "3"))


@dataclass(frozen=True)
class Settings:
    mongo: MongoConfig = MongoConfig()
    neo4j: Neo4jConfig = Neo4jConfig()
    cassandra: CassandraConfig = CassandraConfig()
    redis: RedisConfig = RedisConfig()
    influx: InfluxConfig = InfluxConfig()
    iris: IrisConfig = IrisConfig()


settings = Settings()
