#!/usr/bin/env bash
# Compila todas las clases de scripts/Fixture/ dentro del contenedor (namespace USER).
set -euo pipefail
docker exec -i fixture2030-iris iris session IRIS -U USER '##class(%SYSTEM.OBJ).LoadDir("/scripts/Fixture","ck")'
