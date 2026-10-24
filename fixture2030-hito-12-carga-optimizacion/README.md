# Hito 12 - Pruebas de carga y optimización (Grupo 7)

Medimos cómo se comporta la API del Hito 10 en el momento de más tráfico del
Fixture: hinchas mirando un partido en vivo, que leen comentarios (Cassandra),
publican comentarios y miran las estadísticas de los últimos 5 minutos
(InfluxDB). Sacamos una línea base, encontramos un cuello de botella, lo
corregimos y repetimos exactamente la misma prueba para comparar. También
verificamos que no se pierdan ni se dupliquen datos, y proponemos un Data Mart
para una pregunta analítica.

**Resultado en una línea**: el adaptador de InfluxDB creaba un cliente HTTP
nuevo por consulta, y eso costaba más CPU que la consulta misma. Reutilizando
un solo cliente, a la misma carga bajan mucho la latencia de las estadísticas
y la CPU de la API, y también bajan los p95 y p99 de las rutas de comentarios. Los números
están en `docs/evidencia/comparacion.md`.

## Qué hay en esta carpeta

```
compose-o-instrucciones-del-entorno.md   qué hay que tener levantado y límites de la notebook
config/configuracion-ejemplo.env         parámetros del escenario (sin secretos)
scripts/
  preparar_datos.py            datos de laboratorio en un keyspace y una base propios
  probar_hipotesis.py          prueba aislada del cliente HTTP (antes de optimizar)
  ejecutar_carga.py            levanta una API de prueba, genera la carga y mide
  validar_integridad.py        compara lo aceptado por la API con lo que hay en las bases
  comparar.py                  tabla y gráfico línea base vs optimizada
  limpiar_datos_de_prueba.py   borra solo los datos de esta prueba
  ejecutar_linea_base.sh       preparar + hipótesis + carga + integridad (modo línea base)
  ejecutar_prueba_optimizada.sh   carga + integridad (modo optimizado) + comparación
datos-o-generadores/README.md  cómo son los datos de prueba
docs/                          análisis (ver tabla de abajo)
docs/evidencia/                lo que generan los scripts + capturas
```

El cambio de código está en la API del Hito 10:
`app/adapters/influx_adapter.py` y una variable en `app/config.py`
(`INFLUX_REUSAR_CLIENTE`).

## Cómo correrlo

Requisitos: las bases del Hito 10 levantadas y sembradas, y su venv creado
(ver `compose-o-instrucciones-del-entorno.md`). No hace falta tener la API
corriendo: la prueba levanta la suya en el puerto 8010.

```bash
cd fixture2030-hito-12-carga-optimizacion

# 0. Commitear antes de medir, para que el commit de la evidencia sea el código que se probó
git add -A && git commit -m "..."

# 1. Línea base (~2 min): prepara los datos, prueba la hipótesis, carga con la API como en el Hito 10
bash scripts/ejecutar_linea_base.sh

# 2. Misma prueba con el cambio activado (~2 min), integridad y comparación
bash scripts/ejecutar_prueba_optimizada.sh
```

Cada paso también se puede correr por separado con el Python del venv del
Hito 10 (`../fixture2030-hito-10-api-integrada/.venv/Scripts/python.exe` en
Windows, `.venv/bin/python` en Linux):

```bash
python scripts/preparar_datos.py
python scripts/probar_hipotesis.py
python scripts/ejecutar_carga.py --modo linea_base      # o --modo optimizada
python scripts/validar_integridad.py --modo linea_base
python scripts/comparar.py
```

Para cambiar el escenario (usuarios, duración, mezcla), copiar
`config/configuracion-ejemplo.env` a `config/local.env` y editarlo. Los valores
usados quedan guardados en cada resultado.

**Limpieza (opcional)**: `python scripts/limpiar_datos_de_prueba.py --confirmar`
borra el keyspace `fixture2030_h12`, la base `fixture2030_h12` de InfluxDB y
la carpeta `trabajo/`. No toca los datos del Hito 10, los volúmenes ni
`docs/evidencia/`. Sin `--confirmar` solo muestra lo que borraría.

## Documentación

| Apartado | Dónde |
|---|---|
| Flujo seleccionado, escenario de carga, qué se mide | `docs/flujo_y_escenario_de_carga.md` |
| Datos de prueba | `datos-o-generadores/README.md` |
| Línea base | `docs/linea_base.md` + `docs/evidencia/resultados_linea_base.txt` |
| Hipótesis de cuello de botella, optimización y trade-offs | `docs/hipotesis_y_optimizacion.md` + `docs/evidencia/prueba_hipotesis.txt` |
| Repetición y comparación | `docs/evidencia/resultados_optimizada.txt`, `docs/evidencia/comparacion.md`, `docs/evidencia/grafico_p95.svg` |
| Integridad y limitaciones | `docs/integridad_y_limitaciones.md` + `docs/evidencia/integridad_*.txt` |
| Data Mart | `docs/integracion_data_mart.md` |
| Alternativa relacional | `docs/comparacion_relacional.md` |

**Repetición**: la corrida optimizada usa el mismo commit, la misma
configuración, los mismos datos y la misma secuencia de operaciones por
usuario virtual (semilla fija). Lo único que cambia es
`INFLUX_REUSAR_CLIENTE` (0 → 1). `comparar.py` verifica esas condiciones y
las deja escritas al principio de `comparacion.md`.

## Conclusiones

- **Decisión**: dejamos el cliente compartido (`INFLUX_REUSAR_CLIENTE=1` por
  defecto en el `.env.example` del Hito 10).
- **Mejora observada**: a 60 ops/s, mucho menos p95 y p99 en estadísticas y
  bastante menos CPU de la API. En los comentarios bajan las colas (p95 y
  p99) sin haber tocado Cassandra; la mediana queda parecida. El throughput es el mismo porque las dos versiones llegan
  a la tasa objetivo: la ganancia es margen, no más ops/s medidas.
- **Trade-offs**: un cliente que vive todo el proceso, un límite explícito de
  20 conexiones (si se llena, 504 por timeout) y conexiones abiertas contra
  InfluxDB aunque no haya tráfico.
- **Integridad**: sin pérdidas ni duplicados en la carga. Encontramos que un
  reintento con la misma clave de idempotencia duplica el comentario. Es un
  problema del Hito 10, no de la optimización; está documentado con su
  arreglo propuesto.
- **Próximos pasos**: prueba de capacidad por escalones para encontrar el
  límite de cada versión, arreglo de la idempotencia (midiendo su costo con
  este mismo escenario) y construir el ETL del Data Mart.

Lo que medimos vale para esta notebook, este volumen y esta carga. Qué no se
puede generalizar está en `docs/integridad_y_limitaciones.md`.

## Seguridad

No se versionan `.env`, tokens ni passwords: los scripts leen el token de
InfluxDB del `.env` del Hito 10 (que está en su `.gitignore`) y nunca lo
escriben en la evidencia. `config/local.env` y `trabajo/` también están
ignorados.
