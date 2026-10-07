# Seguridad local, pruebas y evidencia

## 1. Seguridad local

| Elemento | Tratamiento |
|---|---|
| Token de administración | Lo crea `scripts/inicializacion.sh` la primera vez y lo guarda solo en `.influxdb3-token` con permiso 600. Nunca se imprime en pantalla ni en los archivos de evidencia. |
| `.gitignore` | Excluye `.influxdb3-token`, `*.token`, `.env`, `*.local`, `data/` y `*.lp`. |
| Puerto | Publicado solo en `127.0.0.1:8181` (no queda expuesto a la red). |
| Capturas | Se toman de la salida de los scripts, que no muestran el token. No capturar `cat .influxdb3-token` ni el historial de la terminal con el token. |
| Credenciales externas | No se usan. |

Antes de cada commit: `git status` no debe listar `.influxdb3-token` ni `data/`.

## 2. Método de prueba

| Paso | Script | Evidencia de texto | Captura |
|---|---|---|---|
| Ambiente | `docker compose up -d`, `docker compose ps` | — | `01_compose_up.png` |
| Inicialización | `inicializacion.sh` | `00_inicializacion.txt` | `02_inicializacion.png` |
| Generación | `generacion_puntos.sh` | `01_generacion.txt` | `03_generacion.png` |
| Carga | `carga_lotes.sh` | `02_carga.txt` | `04_carga.png` |
| Validación | `validacion.sh` | `03_validacion.txt` | `05_validacion_1.png`, `05_validacion_2.png` |
| Consultas | `consultas_temporales.sh` | `04_consultas.txt` | `06_consultas_1.png` a `06_consultas_3.png` |
| Agregaciones | `agregaciones.sh` | `05_agregaciones.txt` | `07_agregaciones_1.png` a `07_agregaciones_3.png` |
| Persistencia | `docker compose down`, `docker compose up -d` + `validacion.sh` | `03_validacion.txt` (última ejecución) | `08_persistencia_1.png` a `08_persistencia_3.png` |

Los `.txt` los generan los scripts automáticamente en `docs/evidencia/`. Las capturas `.png` se guardan en la misma carpeta.

## 3. Resultados observados

| Dato | Valor |
|---|---|
| Fecha de ejecución | 07/10/2026, entre 16:57 y 17:13 UTC |
| Versión de InfluxDB observada | InfluxDB 3 Core 3.12.0, revisión `3ba97c65f1ee4e1f127a8266517d4d2083b7ea39` (imagen `influxdb:3-core`) |
| Ambiente | Windows con Ubuntu en WSL2 (Linux x86_64), Docker 29.7.2, 16 CPU y 16.441.307.136 bytes (≈ 16 GB) de RAM asignados a Docker |
| Puntos generados | 706.151 (8 partidos): 100.800 de `estadisticas`, 604.800 de `audiencia`, 551 de `eventos`, en 19 s |
| Lotes / fallidos / reintentos | 71 / 0 / 0 |
| Tiempo de carga y rendimiento | 71 s, 9.945 puntos/s (incluye un `docker exec` por lote) |
| Validación | Todas las comprobaciones en OK: puntos por tabla, series (16 y 96), tiros (205) y goles (20) consistentes entre fuentes |
| Persistencia | Después de `docker compose down` y `up -d`, la validación volvió a dar todo OK: los 706.151 puntos se conservaron en `~/docker/data/influxdb` |

### Incidencias durante la prueba

| Incidencia | Causa | Corrección |
|---|---|---|
| La primera validación mostró `observado=` vacío en los conteos | El CLI agrega una línea en blanco al final de la salida CSV y el script tomaba esa línea como valor | `valor_unico` descarta las líneas vacías antes de tomar el resultado |
| Al validar 1 s después de `docker compose up -d` las consultas fallaron con `client error (Connect)` | El contenedor estaba iniciado pero el servidor todavía no aceptaba conexiones | Los scripts esperan a que el servidor responda antes de consultar (`esperar_servidor` en `config.sh`) |

En ambos casos los datos estaban bien cargados; el error estaba en la lectura del resultado. Las capturas de evidencia corresponden a las ejecuciones posteriores a cada corrección.

## 4. Limitaciones

- Se cargó un subconjunto (8 partidos) acorde a una notebook; el objetivo de 10M+ se proyecta, no se declara como medido.
- El rendimiento incluye el costo de ejecutar `docker exec` por lote, por lo que es una cota inferior de lo que admite el servidor.
- Los datos son simulados; sirven para validar el modelo, la carga y las consultas, no para sacar conclusiones deportivas.
- La política de retención está definida pero no aplicada en la base del laboratorio.
