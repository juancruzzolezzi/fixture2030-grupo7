# Grafana

Se configura solo al levantar el compose: `provisioning/datasources/` crea la fuente Prometheus
y `provisioning/dashboards/` carga `dashboards/fixture2030.json`. No hay que importar nada a mano.

Dashboard: http://localhost:3000/d/fixture2030 (usuario `admin`, password del `.env`). Rango por
defecto: últimos 15 minutos, refresco cada 15 s. Cada panel tiene una descripción (ícono "i")
con qué significa y qué haríamos ante una señal mala.

| Fila | Paneles | Fuente | Para qué sirve |
|---|---|---|---|
| Disponibilidad | Estado de salud por base, targets | API, `up` | Ver de un vistazo qué está caído |
| Latencia | p95 de la API por ruta, p95 por base, en escala logarítmica | API | Qué módulo está lento; línea roja en 100 ms |
| Volumen | Requests/s, operaciones/s por base, escrituras en Cassandra por partido | API | Dónde está el tráfico en un pico |
| Errores | Proporción de 5xx, fallas por base, respuestas por clase | API | Qué falla y qué base lo origina |
| Comparación | API contra adaptadores; Redis contra MongoDB | API, exporters | Separar un problema de la API de uno de la base |
| Recursos | CPU y memoria del host Docker, memoria de Redis, conexiones | Exporters | Saturación; líneas rojas en los umbrales |

Para editarlo: el dashboard provisionado no se guarda desde la interfaz. Se hace una copia, se
exporta el JSON y se reemplaza `dashboards/fixture2030.json`, así el cambio queda en el historial
de commits.
