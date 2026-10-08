#!/usr/bin/env bash
# Corre la demostracion completa y guarda la salida como evidencia.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p docs/evidencia
docker exec -i fixture2030-iris iris session IRIS -U USER '##class(Fixture.Demo).Ejecutar()' | tee docs/evidencia/salida_demo_completa.txt
