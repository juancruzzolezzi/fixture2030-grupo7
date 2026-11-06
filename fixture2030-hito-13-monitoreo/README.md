# Hito 13 - Monitoreo y defensa final del Fixture 2030 (Grupo 7)

Capa de observabilidad sobre la plataforma de los hitos anteriores: Prometheus
recolecta métricas de la API y de los exporters, Grafana las muestra y las alertas
dicen qué hacer con cada señal. Con eso preparamos la defensa ante la FIFA.

La defensa es sobre las bases y las decisiones de arquitectura. Grafana es un medio
para demostrarlas: ver `docs/defensa_final.md`.

```
notebook
 ├─ API (uvicorn :8000) ── GET /metrics ◄──────────────┐
 │    └─ adaptadores → las seis bases                  │
 └─ Docker                                             │ cada 15 s
      ├─ Hito 10: mongodb neo4j cassandra redis influxdb iris
      └─ Hito 13: prometheus ──────────────────────────┤
                  ├─ redis-exporter   → Redis          │
                  ├─ mongodb-exporter → MongoDB        │
                  ├─ node-exporter    → host Docker    │
                  └─ grafana ◄── consulta a prometheus
```

## Requisitos

Lo mismo que el Hito 10 (Docker Desktop o Docker Engine, Python 3.10+) y los puertos
9090, 3000, 9100, 9121 y 9216 libres. En Windows, los `.sh` se corren con Git Bash.

## Cómo levantarlo, paso a paso

**1. Bases y datos** (si ya están levantadas y sembradas, alcanza con el `up -d`, que
recrea Redis para aplicarle `maxmemory`; no se pierde nada porque usa volumen):

```bash
cd fixture2030-hito-10-api-integrada
cp .env.example .env                   # solo la primera vez; poner passwords propias
docker compose up -d
bash scripts/sembrar_datos.sh
```

**2. API con métricas.** Hay una dependencia nueva, `prometheus-client`:

```bash
source .venv/bin/activate              # Windows (Git Bash): source .venv/Scripts/activate
pip install --only-binary=:all: -r requirements.txt
bash scripts/iniciar_api.sh            # dejarla corriendo en esta terminal
```

**3. Monitoreo**, en otra terminal:

```bash
cd fixture2030-hito-13-monitoreo
cp .env.example .env                   # poner una password para Grafana
bash scripts/iniciar_monitoreo.sh
```

| Qué | Dónde |
|---|---|
| Prometheus, targets | http://localhost:9090/targets |
| Prometheus, alertas | http://localhost:9090/alerts |
| Grafana, dashboard | http://localhost:3000/d/fixture2030 (usuario `admin`, password del `.env`) |
| Métricas de la API | http://localhost:8000/metrics |

**4. Verificar y repetir la demostración.** Con el Python del venv del Hito 10
(`PY=../fixture2030-hito-10-api-integrada/.venv/bin/python`; en Windows,
`.venv/Scripts/python.exe`). Antes hay que commitear, para que la evidencia apunte
al código que se probó:

```bash
$PY scripts/verificar_targets.py            # ~1 min después de levantar. Genera evidencia/prometheus_targets.*
$PY scripts/generar_carga.py                # 3 min. Genera evidencia/resultados_sin_secretos/carga.*
$PY scripts/ejecutar_prueba_controlada.py   # ~3 min. Detiene Redis y lo recupera. Genera evidencia/prueba_de_falla.*
```

`scripts/generar_evidencia.py` corre los tres en orden y saca las capturas (necesita `pip install playwright`).

Los datos de laboratorio son los del Hito 10: `sembrar_datos.sh` los carga. La carga
agrega comentarios propios, separados en el bloque `203006182355`.

**5. Limpieza.** Nunca toca los volúmenes de las bases.

```bash
bash scripts/limpiar_entorno.sh                # apaga el monitoreo y conserva sus métricas
bash scripts/limpiar_entorno.sh --comentarios  # además borra los comentarios de la carga
bash scripts/limpiar_entorno.sh --metricas     # además borra métricas y Grafana (solo h13_*)
```

Las bases siguen levantadas; se apagan aparte, con `docker compose down` **sin** `-v` en el Hito 10.

## Prometheus

- **Intervalo**: scraping y evaluación de reglas cada 15 s (el de la clase).
- **Retención**: 7 días (`--storage.tsdb.retention.time=7d`), alcanza para preparar la defensa.
- **Etiquetas propias**: `capa` (aplicacion, infraestructura o monitoreo) y `componente`.

| Job | Target | Endpoint | Componente | Cómo mide |
|---|---|---|---|---|
| `fixture-api` | `host.docker.internal:8000` | `/metrics` | API integrada y, a través de ella, las seis bases | Directo: instrumentación propia |
| `redis-exporter` | `redis-exporter:9121` | `/metrics` | Redis | Exporter |
| `mongodb-exporter` | `mongodb-exporter:9216` | `/metrics` | MongoDB | Exporter |
| `node-exporter` | `node-exporter:9100` | `/metrics` | Host de Docker | Exporter |
| `prometheus` | `prometheus:9090` | `/metrics` | Prometheus | Directo |

Por qué no están Neo4j, Cassandra, InfluxDB e IRIS como targets: `docs/inventario_de_componentes.md`.

### Validar que un target está UP

En http://localhost:9090/targets tiene que decir `UP`, o desde Prometheus: `up{job="fixture-api"}`
debe dar 1. También `scripts/verificar_targets.py`, que termina con error si alguno está DOWN.

### Investigar un target DOWN

1. Leer `Last error` en `/targets`, que dice el motivo.
2. ¿El servicio está corriendo? `docker compose ps` en esta carpeta; para la API, `curl http://localhost:8000/salud/vivo`.
3. ¿Responde desde la notebook? `curl http://localhost:9121/metrics` (o el puerto que corresponda).
4. **`fixture-api` DOWN con la API funcionando**: Prometheus está en un contenedor y entra por
   `host.docker.internal`. En Windows lo más común es que el firewall bloquee el puerto 8000.
   Probar con `docker exec fixture2030-prometheus wget -qO- http://host.docker.internal:8000/salud/vivo`.
5. **`mongodb-exporter` UP pero `mongodb_up` en 0**: revisar usuario y password en el `.env` del Hito 10
   y `docker compose logs mongodb-exporter`. No pegar esos logs en la evidencia sin mirarlos.
6. Un exporter DOWN no significa que la base esté caída. Comparar con `database_up`, que sale de la API.

## Qué hay en esta carpeta

| Apartado | Dónde |
|---|---|
| Inventario: qué se monitorea, cómo y con qué límites | `docs/inventario_de_componentes.md` |
| Métricas y consultas PromQL explicadas | `docs/metricas_y_consultas.md` |
| Alertas y umbrales | `docs/alertas_y_umbral.md` + `prometheus/reglas-o-alertas.yml` |
| Decisiones de arquitectura, base por base, y mejora transversal | `docs/decisiones_de_arquitectura.md` |
| Medido, objetivo, estimado y no medido | `docs/limitaciones_y_evidencia.md` |
| Defensa: respuesta central y preguntas de la FIFA | `docs/defensa_final.md` |
| Dashboard de Grafana | `grafana/README.md` + `grafana/dashboards/fixture2030.json` |
| Presentación, guion de 20 minutos, demo y plan B | `defensa/` |
| Evidencia | `evidencia/LEEME.md` |

El cambio de código está en la API del Hito 10: `app/metricas.py` y unas líneas en
`app/main.py` y `app/services/comentarios_service.py`. También `docker-compose.yml` (Redis con `maxmemory`).

## Seguridad

No se versionan `.env`, tokens ni passwords. Los scripts buscan en `evidencia/` los valores de
los `.env` y avisan si aparece alguno (sin mostrarlo). Antes de subir una captura de Grafana o
de una terminal, revisar que no se vea ninguna credencial.
