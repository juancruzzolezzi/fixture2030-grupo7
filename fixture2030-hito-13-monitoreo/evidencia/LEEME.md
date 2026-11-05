# Evidencia

Solo cuenta como observado lo que tiene archivo acá. Cada archivo de texto lleva fecha, commit,
archivos sin commitear y entorno en el encabezado. Los generan los scripts: se pisan en cada corrida.

| Archivo | Lo genera | Qué demuestra |
|---|---|---|
| `prometheus_targets.txt` / `.json` | `scripts/verificar_targets.py` | Targets UP, estado de cada base y métricas clave |
| `resultados_sin_secretos/carga.txt` / `.json` | `scripts/generar_carga.py` | Las seis bases con carga: lo que mide el generador y lo que queda en Prometheus |
| `prueba_de_falla.txt` / `.json` | `scripts/ejecutar_prueba_controlada.py` | Antes, durante y después de detener una base; detección, alerta y recuperación |
| `resultados_sin_secretos/carga_durante_falla.txt` | El mismo script | La carga de fondo de esa prueba |
| `dashboards/*.png` | `scripts/generar_evidencia.py` | El dashboard durante cada estado |

## Capturas de Grafana y Prometheus

Las saca `scripts/generar_evidencia.py` en cada momento de la corrida (`scripts/capturar.py` saca una suelta):

1. `dashboards/01_estado_normal.png`: todas las bases en OK, sin carga.
2. `dashboards/02_durante_carga.png`: el dashboard durante `generar_carga.py`.
3. `dashboards/03_falla_redis.png`: Redis en CAIDA y los 5xx.
4. `dashboards/04_recuperacion.png`: el rango completo de la prueba de falla.
5. `dashboards/05_alertas_prometheus.png`: `/alerts` con `BaseDeDatosCaida` en firing.
6. `dashboards/06_targets_prometheus.png`: `/targets`.

Antes de subirlas hay que mirarlas: no debe verse ninguna credencial.

## `validacion_previa/`

Es una corrida de verificación de los scripts y de la configuración, en un entorno **sin Docker**
y con solo dos de las seis bases. Sirve para saber que la instrumentación funciona; **no es la
evidencia de la plataforma** y no hay que presentarla como tal. Ver `validacion_previa/LEEME.md`.
