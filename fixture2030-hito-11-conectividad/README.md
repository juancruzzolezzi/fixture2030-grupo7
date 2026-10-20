# Hito 11 - Evaluación de la conectividad (Grupo 7)

En este hito evaluamos si la API del Hito 10 puede conectarse y usar de verdad
cada una de las 6 bases. No alcanza con que el contenedor esté levantado: hay
que ver si el nombre resuelve, si el puerto responde, si el protocolo es el
correcto, si las credenciales andan, si existe la base/keyspace/namespace y si
se puede leer un dato. También probamos qué hace la API cuando una base se cae.

La API sigue estando en `fixture2030-hito-10-api-integrada/`. Para este hito le
hicimos algunos cambios (salud, timeouts, reconexión de IRIS, código de partido
único); están listados al final de su README.

## Qué hay en esta carpeta

```
scripts/evaluar_conectividad.py   prueba todo por capas (modos: completo, tcp, nativos, api)
scripts/escenario_falla.sh        detiene o pausa una base, prueba la API y la recupera
config/configuracion-ejemplo.env  URL de la API, portales y timeout (sin secretos)
docs/                             mapa de dependencias, topología, matriz, fallas, health/readiness
docs/evidencia/                   salidas que generan los scripts + capturas
```

## Cómo correrlo

1. Levantar las bases y la API del Hito 10 (README del Hito 10, pasos 1 a 3):

```bash
cd ../fixture2030-hito-10-api-integrada
cp .env.example .env                   # y poner passwords propias en los CAMBIAR_...
docker compose up -d
bash scripts/sembrar_datos.sh          # carga datos y copia el token de Influx al .env
bash scripts/iniciar_api.sh            # deja la API en :8000 y el log en api.log
```

2. En otra terminal, desde esta carpeta, correr la evaluación con el Python del
   venv del Hito 10 (ya tiene todos los drivers):

```bash
cd fixture2030-hito-11-conectividad
../fixture2030-hito-10-api-integrada/.venv/bin/python scripts/evaluar_conectividad.py
```

Se puede correr por partes: `--modo tcp`, `--modo nativos`, `--modo api`, o un
solo producto con `--producto redis`. Una prueba solo queda OK si el resultado
es el esperado (status, dato leído, cantidad); si no, queda FALLA. Cada corrida guarda su salida en
`docs/evidencia/` y arma `docs/evidencia/matriz.md`.

3. Escenarios de falla (con la API corriendo):

```bash
bash scripts/escenario_falla.sh redis              # base detenida -> 503
bash scripts/escenario_falla.sh influxdb pausar    # base congelada -> 504 por timeout
bash scripts/escenario_falla.sh iris               # IRIS se reinicia y la API se reconecta sola
```

Los escenarios usan `docker compose stop/start` y `pause/unpause`. No se borra
ningún volumen ni dato. Para apagar todo sin perder datos: `docker compose down`
(sin `-v`).

## Cómo leer los resultados

- `OK`: esa prueba funcionó. No quiere decir que la base vaya a aguantar carga.
- `FALLA`: se ejecutó y falló. El detalle dice en qué capa.
- `SKIP`: no se ejecutó porque faltaba una herramienta o una variable. No quiere
  decir que la base esté caída.
- `N/A`: la capa no existe en nuestro laboratorio (por ejemplo, Cassandra y
  Redis no tienen usuario/password).
- `NO_EJECUTADA`: falló una capa anterior, así que no tenía sentido seguir.

Las passwords y el token de Influx nunca se muestran: el script los reemplaza
por `***` antes de imprimir o guardar.

## Limitaciones

- Cassandra y Redis no tienen autenticación y Neo4j Community no tiene roles,
  así que esas capas quedan en `N/A`.
- El cliente de línea de comandos de cada base (mongosh, cqlsh, etc.) se usa con
  `docker exec`, o sea desde adentro del contenedor de la base, no desde donde
  corre la API.
- Probamos con la API en la notebook. No la corrimos dentro de un contenedor
  (ver `docs/topologia_y_entornos.md`).
- Los tiempos que aparecen son de una sola request, sin carga. Las pruebas de
  carga son del Hito 12.
