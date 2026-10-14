# -*- coding: utf-8 -*-
"""
Carga reproducible de Equipos y Jugadores del Fixture 2030 (Hito 4 - Grupo 7).

Qué hace:
  1. Genera 64 equipos y un plantel sintético por equipo (20-24 jugadores c/u),
     con una semilla fija (ver seed/datos_referencia.py) -> siempre el mismo dataset.
  2. Carga todo a MongoDB con upsert por _id: correr este script una segunda vez
     actualiza los documentos existentes en vez de duplicarlos (RF8).
  3. Crea los tres índices justificados en el documento de decisiones (ver
     Grupo_7_Hito_4_Decisiones_Documentales_Fixture2030).
  4. Imprime un resumen con las cantidades finales, para usar como evidencia de carga.

Requiere: pymongo (ver requirements.txt) y una instancia de MongoDB accesible en MONGO_URI.

Uso:
    python generate_and_load.py
"""

import os
import random
import sys
from datetime import date, timedelta

from pymongo import ASCENDING, DESCENDING, MongoClient, UpdateOne
from pymongo.errors import ConnectionFailure

sys.path.insert(0, os.path.dirname(__file__))
from datos_referencia import (
    APELLIDOS,
    COMPOSICION_PLANTEL,
    EQUIPOS,
    NOMBRES,
    PIE_HABIL,
    SEED,
    origen_de,
    rng_para_equipo,
)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://fixture_admin:fixture2030@localhost:27017/?authSource=admin")
DB_NAME = os.environ.get("MONGO_DB", "fixture2030")


# ---------------------------------------------------------------------------
# Generación determinística de un plantel
# ---------------------------------------------------------------------------
def generar_plantel(codigo_equipo: str, confederacion: str) -> list[dict]:
    rng = rng_para_equipo(codigo_equipo)
    origen = origen_de(codigo_equipo, confederacion)
    nombres_pool = NOMBRES[origen]
    apellidos_pool = APELLIDOS[origen]

    # Tamaño de plantel variable (24-26, como los planteles reales de un Mundial),
    # determinístico por equipo
    extra = rng.randint(0, 2)
    composicion = list(COMPOSICION_PLANTEL)
    for _ in range(extra):
        pos = rng.choice(["Defensor", "Mediocampista", "Delantero"])
        composicion = [(p, n + 1) if p == pos else (p, n) for p, n in composicion]

    tamanio_plantel = sum(n for _, n in composicion)
    # Dorsales 1..tamanio_plantel, sin huecos: así cualquier número por encima
    # del tamaño del plantel (27, 28, 29...) queda libre en TODOS los equipos y
    # sirve para demostrar una convocatoria nueva sin chocar con un dorsal ya
    # asignado (ver queries/01_insercion.py).
    dorsales_disponibles = list(range(1, tamanio_plantel + 1))
    rng.shuffle(dorsales_disponibles)

    jugadores = []
    dorsal_idx = 0
    hoy = date(2026, 9, 4)
    for posicion, cantidad in composicion:
        for _ in range(cantidad):
            dorsal = dorsales_disponibles[dorsal_idx]
            dorsal_idx += 1
            nombre = rng.choice(nombres_pool)
            apellido = rng.choice(apellidos_pool)
            edad = rng.randint(18, 37)
            fecha_nacimiento = hoy - timedelta(days=edad * 365 + rng.randint(0, 364))

            # Estadísticas sintéticas, correlacionadas con la posición (un arquero no
            # convierte goles con la misma frecuencia que un delantero).
            partidos = rng.randint(5, 90)
            if posicion == "Delantero":
                goles = rng.randint(1, max(1, partidos // 2))
                asistencias = rng.randint(0, partidos // 4)
            elif posicion == "Mediocampista":
                goles = rng.randint(0, partidos // 4)
                asistencias = rng.randint(1, partidos // 3)
            elif posicion == "Defensor":
                goles = rng.randint(0, partidos // 10)
                asistencias = rng.randint(0, partidos // 8)
            else:  # Arquero
                goles = 0
                asistencias = 0

            jugador = {
                "_id": f"{codigo_equipo}-{dorsal:02d}",
                "equipo_id": codigo_equipo,
                # Referencia extendida: copiamos 2 campos de lectura frecuente del
                # equipo para evitar un $lookup en la consulta más común (ver
                # documento de decisiones, sección "Relación equipo-jugador").
                "equipo_resumen": {"nombre": None, "confederacion": confederacion},
                "nombre": nombre,
                "apellido": apellido,
                "dorsal": dorsal,
                "posicion": posicion,
                "fecha_nacimiento": fecha_nacimiento.isoformat(),
                "altura_cm": rng.randint(165, 200),
                "pie_habil": rng.choice(PIE_HABIL),
                "estadisticas": {
                    "partidos_jugados": partidos,
                    "goles": goles,
                    "asistencias": asistencias,
                    "tarjetas_amarillas": rng.randint(0, partidos // 6),
                    "tarjetas_rojas": rng.randint(0, 2),
                },
            }
            jugadores.append(jugador)
    return jugadores


def generar_equipo(codigo, nombre, confederacion, sede) -> dict:
    rng = rng_para_equipo(codigo + "-staff")
    return {
        "_id": codigo,
        "nombre": nombre,
        "confederacion": confederacion,
        "sede_mundial": sede,
        "ranking_fifa": rng.randint(1, 210),
        "entrenador": {
            "nombre": f"{rng.choice(NOMBRES['hispano'])} {rng.choice(APELLIDOS['hispano'])}",
        },
        # Denormalizado y mantenido por la carga/actualización, no por el cliente:
        # evita tener que contar jugadores en cada lectura de la ficha del equipo.
        "cantidad_jugadores": None,  # se completa después de generar el plantel
    }


def generar_dataset():
    equipos_docs = []
    jugadores_docs = []
    for codigo, nombre, confederacion, sede in EQUIPOS:
        equipo = generar_equipo(codigo, nombre, confederacion, sede)
        plantel = generar_plantel(codigo, confederacion)
        for j in plantel:
            j["equipo_resumen"]["nombre"] = nombre
        equipo["cantidad_jugadores"] = len(plantel)
        equipos_docs.append(equipo)
        jugadores_docs.extend(plantel)
    return equipos_docs, jugadores_docs


# ---------------------------------------------------------------------------
# Carga idempotente
# ---------------------------------------------------------------------------
def cargar(db, equipos_docs, jugadores_docs):
    ops_equipos = [
        UpdateOne({"_id": e["_id"]}, {"$set": e}, upsert=True) for e in equipos_docs
    ]
    res_e = db.equipos.bulk_write(ops_equipos, ordered=False)

    ops_jugadores = [
        UpdateOne({"_id": j["_id"]}, {"$set": j}, upsert=True) for j in jugadores_docs
    ]
    res_j = db.jugadores.bulk_write(ops_jugadores, ordered=False)
    return res_e, res_j


def crear_indices(db):
    """
    Los tres índices están justificados uno por uno en el documento de decisiones.
    No creamos ningún índice "por las dudas": cada uno responde a una consulta
    concreta de queries/.
    """
    db.jugadores.create_index(
        [("equipo_id", ASCENDING), ("posicion", ASCENDING)],
        name="ix_equipo_posicion",
    )
    db.jugadores.create_index(
        [("estadisticas.goles", DESCENDING)],
        name="ix_goles_desc",
    )
    db.equipos.create_index(
        [("confederacion", ASCENDING)],
        name="ix_confederacion",
    )


def verificar_integridad(db):
    """Chequeo de aplicación, además de la validación $jsonSchema: todo jugador
    debe apuntar a un equipo_id que exista en la colección equipos (RNF3)."""
    codigos_equipo = {e["_id"] for e in db.equipos.find({}, {"_id": 1})}
    huerfanos = db.jugadores.count_documents({"equipo_id": {"$nin": list(codigos_equipo)}})
    return huerfanos


def main():
    print(f"Conectando a {MONGO_URI.split('@')[-1]} (semilla={SEED})...")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
    except ConnectionFailure as e:
        print("No se pudo conectar a MongoDB. ¿Está corriendo `docker compose up -d`?")
        raise SystemExit(1) from e

    db = client[DB_NAME]

    equipos_docs, jugadores_docs = generar_dataset()
    print(f"Generados {len(equipos_docs)} equipos y {len(jugadores_docs)} jugadores (en memoria).")

    res_e, res_j = cargar(db, equipos_docs, jugadores_docs)
    print(f"Equipos   -> upserted={res_e.upserted_count} modificados={res_e.modified_count} "
          f"coincidentes={res_e.matched_count}")
    print(f"Jugadores -> upserted={res_j.upserted_count} modificados={res_j.modified_count} "
          f"coincidentes={res_j.matched_count}")

    crear_indices(db)
    print("Índices creados/verificados: ix_equipo_posicion, ix_goles_desc, ix_confederacion")

    total_equipos = db.equipos.count_documents({})
    total_jugadores = db.jugadores.count_documents({})
    huerfanos = verificar_integridad(db)

    print("\n--- Resumen final (evidencia de carga) ---")
    print(f"Equipos en la base:   {total_equipos} (esperado: 64)")
    print(f"Jugadores en la base: {total_jugadores} (esperado: >= 1000)")
    print(f"Jugadores sin equipo válido: {huerfanos} (esperado: 0)")
    assert total_equipos == 64, "no hay 64 equipos, revisar datos_referencia.py"
    assert total_jugadores >= 1000, "no se alcanzó el volumen mínimo de RNF2"
    assert huerfanos == 0, "hay jugadores con equipo_id inválido"
    print("OK: RF4, RF5, RF8 y RNF2/RNF3 verificados sobre el estado actual de la base.")


if __name__ == "__main__":
    main()
