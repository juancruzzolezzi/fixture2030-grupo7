# Cardinalidad y escalabilidad

## 1. Variación de cada dimensión

| Tag | Tabla | Valores distintos | Acotada | Justificación como tag |
|---|---|---|---|---|
| `partido_id` | las tres | 127 | Sí | Filtro de casi todos los patrones |
| `equipo_id` | estadisticas, eventos | 64 | Sí | Comparar equipos (PA1, PA3, PA7) |
| `sede` | estadisticas | 6 | Sí | Filtro por sede (PA4) |
| `region` | audiencia | 12 | Sí | Pico por región (PA5) |
| `tipo_evento` | eventos | 4 | Sí | Contar por tipo (PA6, PA9) |

## 2. Estimación de series

La clase plantea el producto teórico de las dimensiones (64 equipos × 127 partidos × 6 sedes = 48.768). En este modelo las combinaciones **reales** son mucho menores porque las dimensiones no son independientes:

- cada partido tiene exactamente **2 equipos**;
- cada partido se juega en **1 sola sede**, así que `sede` depende de `partido_id` y no agrega series nuevas.

| Tabla | Combinación que forma la serie | Series reales en el torneo | Puntos por serie |
|---|---|---|---|
| estadisticas | partido × equipo × sede = 127 × 2 × 1 | **254** | 6.300 |
| audiencia | partido × región = 127 × 12 | **1.524** | 6.300 |
| eventos | partido × equipo × tipo ≤ 127 × 2 × 4 | **≤ 1.016** | ≈ 9 |
| **Total** | | **≤ 2.794 series** | |

Con ≈ 11,2 millones de puntos y menos de 2.800 series, cada serie acumula miles de puntos: la cantidad de series queda acotada por las dimensiones del torneo y **no crece con el volumen**. Eso es lo que se busca según la Clase 9.

La validación mide las series efectivamente cargadas en la prueba local (`scripts/validacion.sh`, sección 2) con `SELECT DISTINCT` sobre los tags de cada tabla:

| Tabla | Series esperadas (8 partidos) | Series medidas | Resultado |
|---|---|---|---|
| estadisticas | 8 × 2 = 16 | 16 | OK: `sede` no agregó series |
| audiencia | 8 × 12 = 96 | 96 | OK |
| eventos | ≤ 8 × 2 × 4 = 64 | 58 | Dentro del máximo (no todos los equipos registraron los 4 tipos, por ejemplo POR no hizo goles en M001) |

Evidencia: `docs/evidencia/03_validacion.txt` y capturas `05_validacion_*.png`.

## 3. Atributos excluidos de los tags

| Atributo | Dónde queda | Por qué no es tag |
|---|---|---|
| Identificador de usuario | No se guarda (vive en Redis, Hito 7) | Millones de valores: dimensión explosiva. Para el pico por región basta el total de usuarios. |
| Identificador único de evento | No se guarda | Un valor por punto: la cantidad de series se aproximaría al volumen total. El evento queda identificado por tabla + tags + tiempo. |
| `dorsal` | Field en `eventos` | No es filtro de ningún patrón prioritario; como tag multiplicaría las series de eventos hasta × 26. |
| `minuto` | Field en `eventos` | Se deriva del timestamp y cambia en cada punto. |
| `posesion_pct`, `pases_completados`, `tiros`, `usuarios_conectados` | Fields | Son valores medidos de variación continua. |
| Timestamp | Columna `time` | Usar el tiempo como tag es el error frecuente señalado en clase. |

## 4. Escalabilidad hacia 10M+ puntos

| Aspecto | Decisión | Riesgo controlado |
|---|---|---|
| Frecuencia | 1 muestra por segundo por equipo y por región (14 puntos/s por partido en vivo, más los eventos) | El volumen total se calcula de antemano (ver `patrones_de_acceso.md`) |
| Batching | Lotes de 10.000 líneas (`LOTE`), configurable | Evita un punto por solicitud y lotes demasiado grandes |
| Concurrencia | 1 en la prueba local | No saturar una notebook; ver carga proyectada abajo |
| Cardinalidad | ≤ 2.794 series, todas las dimensiones acotadas | Sin tags de alta variación |
| Consulta | Todas las consultas acotan rango temporal y dimensiones | Una pantalla en vivo nunca lee el histórico completo |
| Retención | Datos crudos con vencimiento + resúmenes históricos (ver `retencion_y_granularidad.md`) | El almacenamiento no crece sin límite |

### Prueba local vs objetivo

| | Prueba local (ejecutada) | Objetivo de diseño (proyectado) |
|---|---|---|
| Partidos | 8 (`PARTIDOS=8`) | 127 (`PARTIDOS=127`) |
| Puntos | 706.151 (medido) | ≈ 11.210.000 |
| Lotes | 71 de 10.000 líneas, 0 fallidos | ≈ 1.121 lotes |
| Tiempo de carga | 71 s (medido) | ≈ 1.127 s ≈ 19 min (proyectado) |
| Rendimiento | 9.945 puntos/s (medido) | No se declara sin ejecutarlo |
| Ambiente | InfluxDB 3 Core 3.12.0, Docker 29.7.2, 16 CPU y ≈ 16 GB de RAM asignados a Docker, Ubuntu en WSL2 | — |

Evidencia: `docs/evidencia/02_carga.txt` y captura `04_carga.png`.

**Proyección:** con el rendimiento medido, cargar 11,2M puntos llevaría `11.210.000 / 9.945 ≈ 1.127 s` (≈ 19 minutos). Es una **estimación** que supone el mismo rendimiento a mayor volumen; no es una medición.

**Lectura del resultado:** los 71 lotes tardaron ≈ 1 s cada uno, y ese segundo incluye abrir un `docker exec` por lote. Con lotes más grandes o varias cargas en paralelo el tiempo bajaría, pero eso habría que medirlo antes de afirmarlo.

### Qué cambiaría al crecer

- **Más fuentes** (por ejemplo, velocidad o presión por jugador): nuevas tablas con sus propias dimensiones acotadas, evaluando la cardinalidad antes de agregar tags.
- **Carga distribuida**: en un torneo real los partidos simultáneos son a lo sumo 4; cada fuente escribe sus propios lotes en paralelo (concurrencia = cantidad de partidos en juego), y el lote se ajusta midiendo, no suponiendo.
- **Observabilidad posterior**: la tabla `audiencia` ya es una métrica operativa; nuevas métricas (latencia, errores) seguirían el mismo modelo.
