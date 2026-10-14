# -*- coding: utf-8 -*-
"""
Configuracion de la API (Hito 10, Grupo 7).

Todo lo que es host/puerto/credencial sale de variables de entorno (RNF6).
Nada de esto tiene un valor por defecto que sea un secreto real: son los
valores del ambiente local de laboratorio, los mismos que ya documentaron
los Hitos 4 a 9 para cada base.
"""

import os
from dataclasses import dataclass


def _env(nombre: str, default: str) -> str:
    return os.environ.get(nombre, default)


@dataclass(frozen=True)
class MongoConfig:
    uri: str = _env("MONGO_URI", "mongodb://fixture_admin:fixture2030@localhost:27017/?authSource=admin")
    db: str = _env("MONGO_DB", "fixture2030")
    timeout_ms: int = int(_env("MONGO_TIMEOUT_MS", "3000"))


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str = _env("NEO4J_URI", "bolt://localhost:7687")
    usuario: str = _env("NEO4J_USER", "neo4j")
    password: str = _env("NEO4J_PASSWORD", "fixture2030_local")
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


@dataclass(frozen=True)
class IrisConfig:
    hostname: str = _env("IRIS_HOST", "localhost")
    puerto: int = int(_env("IRIS_PORT", "1972"))
    namespace: str = _env("IRIS_NAMESPACE", "USER")
    usuario: str = _env("IRIS_USER", "_SYSTEM")
    password: str = _env("IRIS_PASSWORD", "SYS")
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
