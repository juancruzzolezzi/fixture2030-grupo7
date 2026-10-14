# -*- coding: utf-8 -*-
"""
Datos de referencia para generar el dataset sintético y reproducible del Fixture 2030.

Todo lo que hay acá es determinístico: mismos equipos, mismo orden, misma semilla de
generación aleatoria. Correr generate_and_load.py dos veces produce exactamente los mismos
documentos (RF8 / RNF1).

Los 64 equipos son una selección propia para completar el escenario ficticio de 64
selecciones que plantea el TPO (el Mundial 2030 real todavía no tiene su fixture definido).
Usamos nombres reales de selecciones nacionales -son entidades públicas, no personas- y
generamos jugadores, dorsales y estadísticas sintéticos: no representan personas reales.
"""

import random

SEED = 20260 + 4  # Fixture 2030, Hito 4 -> semilla fija y explicable

# ---------------------------------------------------------------------------
# 64 equipos: código FIFA de 3 letras (va a ser el _id de "equipos"), nombre,
# confederación y si es uno de los seis países sede (juegan de local, no clasifican
# por deporte, dato que ya habíamos usado en Hitos 1-3).
# ---------------------------------------------------------------------------
EQUIPOS = [
    # Sedes (clasificación automática, tal como establece el reglamento del Mundial 2030)
    ("ARG", "Argentina", "CONMEBOL", True),
    ("PAR", "Paraguay", "CONMEBOL", True),
    ("URU", "Uruguay", "CONMEBOL", True),
    ("ESP", "España", "UEFA", True),
    ("POR", "Portugal", "UEFA", True),
    ("MAR", "Marruecos", "CAF", True),
    # Resto de CONMEBOL
    ("BRA", "Brasil", "CONMEBOL", False),
    ("COL", "Colombia", "CONMEBOL", False),
    ("ECU", "Ecuador", "CONMEBOL", False),
    ("CHI", "Chile", "CONMEBOL", False),
    ("PER", "Perú", "CONMEBOL", False),
    ("BOL", "Bolivia", "CONMEBOL", False),
    ("VEN", "Venezuela", "CONMEBOL", False),
    # UEFA
    ("FRA", "Francia", "UEFA", False),
    ("ALE", "Alemania", "UEFA", False),
    ("ING", "Inglaterra", "UEFA", False),
    ("ITA", "Italia", "UEFA", False),
    ("HOL", "Países Bajos", "UEFA", False),
    ("BEL", "Bélgica", "UEFA", False),
    ("CRO", "Croacia", "UEFA", False),
    ("SUI", "Suiza", "UEFA", False),
    ("DIN", "Dinamarca", "UEFA", False),
    ("POL", "Polonia", "UEFA", False),
    ("SER", "Serbia", "UEFA", False),
    ("AUT", "Austria", "UEFA", False),
    ("UCR", "Ucrania", "UEFA", False),
    ("GAL", "Gales", "UEFA", False),
    ("ESC", "Escocia", "UEFA", False),
    ("SUE", "Suecia", "UEFA", False),
    ("NOR", "Noruega", "UEFA", False),
    ("TUR", "Turquía", "UEFA", False),
    ("RUM", "Rumania", "UEFA", False),
    ("HUN", "Hungría", "UEFA", False),
    ("REP", "República Checa", "UEFA", False),
    ("GRE", "Grecia", "UEFA", False),
    # CAF
    ("SEN", "Senegal", "CAF", False),
    ("NGA", "Nigeria", "CAF", False),
    ("EGI", "Egipto", "CAF", False),
    ("CAM", "Camerún", "CAF", False),
    ("GHA", "Ghana", "CAF", False),
    ("TUN", "Túnez", "CAF", False),
    ("COS", "Costa de Marfil", "CAF", False),
    ("MAL", "Malí", "CAF", False),
    ("ARB", "Argelia", "CAF", False),
    ("SUD", "Sudáfrica", "CAF", False),
    # AFC
    ("JAP", "Japón", "AFC", False),
    ("COR", "Corea del Sur", "AFC", False),
    ("AUS", "Australia", "AFC", False),
    ("IRN", "Irán", "AFC", False),
    ("ARS", "Arabia Saudita", "AFC", False),
    ("QAT", "Catar", "AFC", False),
    ("IRQ", "Irak", "AFC", False),
    ("UZB", "Uzbekistán", "AFC", False),
    ("JOR", "Jordania", "AFC", False),
    # CONCACAF
    ("MEX", "México", "CONCACAF", False),
    ("USA", "Estados Unidos", "CONCACAF", False),
    ("CAN", "Canadá", "CONCACAF", False),
    ("CRC", "Costa Rica", "CONCACAF", False),
    ("JAM", "Jamaica", "CONCACAF", False),
    ("PAN", "Panamá", "CONCACAF", False),
    ("HON", "Honduras", "CONCACAF", False),
    # OFC
    ("NZL", "Nueva Zelanda", "OFC", False),
    # Repechaje / ampliación a 64 (intercontinental, tal como define el reglamento)
    ("CVE", "Cabo Verde", "CAF", False),
    ("UAE", "Emiratos Árabes Unidos", "AFC", False),
]
assert len(EQUIPOS) == 64, len(EQUIPOS)
assert len({c for c, *_ in EQUIPOS}) == 64, "hay códigos de equipo repetidos"

CONFEDERACIONES = sorted({conf for _, _, conf, _ in EQUIPOS})

# ---------------------------------------------------------------------------
# Pools de nombres para generar jugadores. No son bases de datos de personas reales:
# son listas de nombres y apellidos comunes en distintas regiones, combinados al azar
# (con semilla fija) para armar identidades sintéticas.
# ---------------------------------------------------------------------------
NOMBRES = {
    "hispano": ["Mateo", "Santiago", "Lucas", "Benjamín", "Joaquín", "Thiago", "Facundo",
                "Agustín", "Nicolás", "Emiliano", "Franco", "Gonzalo", "Rodrigo", "Bruno",
                "Ignacio", "Martín", "Diego", "Julián", "Tomás", "Federico"],
    "luso": ["João", "Pedro", "Rafael", "Gabriel", "Bruno", "Ricardo", "Tiago", "André",
             "Bernardo", "Diogo", "Rúben", "Gonçalo", "Vítor", "Nuno", "Hugo"],
    "anglo": ["Jack", "James", "Oliver", "Harry", "George", "Noah", "Ethan", "Callum",
              "Ryan", "Connor", "Liam", "Mason", "Tyler", "Jordan", "Owen"],
    "arabe": ["Mohamed", "Ahmed", "Youssef", "Karim", "Omar", "Ali", "Hassan", "Amir",
              "Khalid", "Sami", "Tariq", "Rachid", "Adil", "Nabil", "Yassine"],
    "otros": ["Erik", "Lukas", "Mikael", "Viktor", "Jan", "Marek", "Dario", "Ivan",
              "Kenji", "Haruto", "Minjun", "Kwame", "Chidi", "Sipho", "Amadou"],
}
APELLIDOS = {
    "hispano": ["González", "Rodríguez", "Fernández", "López", "Martínez", "Pérez",
                "Sánchez", "Romero", "Díaz", "Torres", "Flores", "Acosta", "Benítez",
                "Cabrera", "Vega", "Molina", "Herrera", "Aguirre", "Ríos", "Silva"],
    "luso": ["Silva", "Santos", "Ferreira", "Costa", "Oliveira", "Pereira", "Carvalho",
             "Rodrigues", "Martins", "Ribeiro", "Sousa", "Gomes", "Lopes", "Marques"],
    "anglo": ["Smith", "Taylor", "Brown", "Wilson", "Evans", "Walker", "Wright", "Clarke",
              "Baker", "Bell", "Cooper", "Ward", "Hughes", "Foster", "Hunt"],
    "arabe": ["El Amrani", "Benali", "Cherkaoui", "Ziani", "Boukhari", "Fassi", "Idrissi",
              "Alaoui", "Bouzid", "Tazi", "Nasser", "Hakimi", "Saadi", "Karrouchi"],
    "otros": ["Nowak", "Kovač", "Andersson", "Nielsen", "Kim", "Tanaka", "Suzuki",
              "Okafor", "Mensah", "Diallo", "Traoré", "Berg", "Novak", "Horvat"],
}

CONF_A_ORIGEN = {
    "CONMEBOL": "hispano", "UEFA": "otros", "CAF": "otros", "AFC": "otros",
    "CONCACAF": "anglo", "OFC": "anglo",
}
# Excepciones de idioma dentro de la confederación (más realistas que el default)
ORIGEN_POR_EQUIPO = {
    "BRA": "luso", "POR": "luso",
    "ESP": "hispano", "MEX": "hispano", "USA": "anglo", "ING": "anglo", "ESC": "anglo",
    "GAL": "anglo", "AUS": "anglo", "CAN": "anglo", "NZL": "anglo", "JAM": "anglo",
    "MAR": "arabe", "EGI": "arabe", "TUN": "arabe", "ARB": "arabe", "ARS": "arabe",
    "QAT": "arabe", "IRQ": "arabe", "JOR": "arabe", "UAE": "arabe",
}

POSICIONES = ["Arquero", "Defensor", "Mediocampista", "Delantero"]
# Composición típica de un plantel de 20-24 jugadores
COMPOSICION_PLANTEL = [("Arquero", 3), ("Defensor", 8), ("Mediocampista", 8), ("Delantero", 5)]

PIE_HABIL = ["Derecho", "Izquierdo", "Ambidiestro"]


def origen_de(codigo_equipo: str, confederacion: str) -> str:
    return ORIGEN_POR_EQUIPO.get(codigo_equipo, CONF_A_ORIGEN[confederacion])


def rng_para_equipo(codigo_equipo: str) -> random.Random:
    """RNG determinístico por equipo: mismo equipo -> mismo plantel, siempre."""
    return random.Random(f"{SEED}-{codigo_equipo}")
