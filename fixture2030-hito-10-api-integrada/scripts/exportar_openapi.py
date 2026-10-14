# -*- coding: utf-8 -*-
"""Vuelca el esquema OpenAPI que genera la propia app a openapi/openapi.yaml
(RF13): nunca se escribe a mano, para que no pueda describir un endpoint que
la aplicacion no tiene (restriccion de la consigna, seccion 5.4)."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.main import app

if __name__ == "__main__":
    esquema = app.openapi()
    destino = Path(__file__).resolve().parent.parent / "openapi" / "openapi.yaml"
    destino.write_text(yaml.safe_dump(esquema, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"OpenAPI exportado a {destino}")
