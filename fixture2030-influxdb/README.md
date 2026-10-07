# Hito 8 — Series temporales de estadísticas en vivo (Fixture 2030)

**Repositorio del grupo:** https://github.com/juancruzzolezzi/fixture2030-grupo7
**Asignatura:** Ingeniería de Datos II — Grupo 7
**Tecnología:** InfluxDB 3 Core (base multidimensional / series temporales) con Docker Compose

Módulo que registra y consulta las estadísticas que cambian segundo a segundo durante los partidos del Mundial 2030: posesión, pases y tiros por equipo, usuarios conectados por región y eventos de juego.

## Estructura

```
fixture2030-influxdb/
├── docker-compose.yml
├── scripts/
│   ├── config.sh                  configuración compartida (sin secretos)
│   ├── inicializacion.sh          ambiente, token local y base de datos
│   ├── generacion_puntos.sh       genera line protocol (data/puntos.lp)
│   ├── carga_lotes.sh             carga por lotes con reintentos y medición
│   ├── validacion.sh              compara lo cargado con lo generado
│   ├── consultas_temporales.sh    ventanas, filtros y comparaciones
│   ├── agregaciones.sh            resúmenes y downsampling
│   └── limpieza.sh                borra datos generados (opcional)
├── docs/
│   ├── patrones_de_acceso.md      problema temporal y patrones
│   ├── modelo_multidimensional.md tablas, tags, fields, series, coherencia con el TPO
│   ├── cardinalidad_y_escalabilidad.md
│   ├── carga_y_consultas.md       carga, consultas, agregaciones e interpretación
│   ├── retencion_y_granularidad.md
│   ├── seguridad_y_evidencia.md   seguridad local, método de prueba y resultados
│   └── evidencia/                 salidas .txt de los scripts y capturas .png
├── .gitignore
└── README.md
```

## Requisitos

- Docker Desktop (o Docker Engine) con Docker Compose.
- Terminal bash (macOS, Linux o WSL en Windows). **En Windows** los scripts no corren en PowerShell: abrir la app **Ubuntu** (WSL) y activar Ubuntu en Docker Desktop → Settings → Resources → WSL integration. La prueba de evidencia se ejecutó así.
- ≈ 1 GB libre para la prueba local de 8 partidos.

## Ejecución paso a paso

Todos los comandos se ejecutan **desde la carpeta `fixture2030-influxdb/`**.

### 1. Preparar la persistencia (una sola vez)

```bash
mkdir -p ~/docker/data/influxdb
sudo chown -R "$(id -u):$(id -g)" ~/docker/data/influxdb
sudo chmod -R 777 ~/docker/data/influxdb
chmod +x scripts/*.sh
```

### 2. Iniciar InfluxDB

```bash
docker compose up -d
docker compose ps
docker compose logs influxdb
```

> Si ya tenés corriendo el contenedor de la demo de la Clase 9 (`fixture2030-influxdb`), ejecutá antes `docker compose down` en la carpeta de la clase. Usa el mismo nombre y la misma carpeta de datos.

### 3. Inicializar (token y base)

```bash
./scripts/inicializacion.sh
```

Crea el token de administración la primera vez y lo guarda en `.influxdb3-token` (no se versiona). Si la instancia ya tenía un token de la demo de clase, copiá ese archivo `.influxdb3-token` a esta carpeta.

### 4. Generar los puntos

```bash
PARTIDOS=8 ./scripts/generacion_puntos.sh
```

Prueba local: 8 partidos ≈ 706.000 puntos. Objetivo de diseño: `PARTIDOS=127` ≈ 11,2 millones.

### 5. Cargar en lotes

```bash
./scripts/carga_lotes.sh
```

Parámetros opcionales: `LOTE=10000 MAX_REINTENTOS=3 ./scripts/carga_lotes.sh`.

### 6. Validar

```bash
./scripts/validacion.sh
```

### 7. Consultas y agregaciones

```bash
./scripts/consultas_temporales.sh
./scripts/agregaciones.sh
```

### 8. Detener y reiniciar sin perder datos

```bash
docker compose down        # detiene y elimina el contenedor
docker compose up -d       # lo vuelve a crear usando la misma carpeta de datos
./scripts/validacion.sh    # comprueba que los puntos siguen ahí
```

Los datos persisten en `~/docker/data/influxdb`, que no se borra con `docker compose down`.

### Limpieza opcional

```bash
./scripts/limpieza.sh      # borra solo data/ (archivos generados)
```

Para empezar de cero toda la instancia, seguir las instrucciones que imprime ese script.

## Problemas frecuentes (Clase 9)

| Error | Solución |
|---|---|
| `exec: influxdb3: not found` | Se inició la imagen 2.x. `docker compose down && docker compose pull && docker compose up -d --force-recreate` |
| `PermissionDenied` en `/var/lib/influxdb3/data` | `docker compose down`, corregir permisos (paso 1) y `docker compose up -d --force-recreate` |
| La validación muestra diferencias después de cambiar `PARTIDOS` | Se mezclaron cargas distintas. Reiniciar la instancia o volver a generar con el mismo `PARTIDOS` que ya se cargó |

## Nota sobre la imagen (RNF1)

El enunciado del hito pide la imagen `influxdb:latest`. La Clase 9 aclara que `influxdb:latest` corresponde a **InfluxDB 2.x** y no incluye el binario `influxdb3`, por lo que no puede ejecutar el comando `influxdb3 serve` ni las herramientas de la práctica. Se usa la imagen oficial **`influxdb:3-core`** con `pull_policy: always`, como en el Compose de la clase: cada `docker compose up -d` descarga la última versión disponible de la línea 3 Core, que es el criterio de actualización que busca el requisito. La versión efectivamente observada queda registrada en `docs/evidencia/00_inicializacion.txt`.

## Seguridad

El token vive solo en `.influxdb3-token`, excluido por `.gitignore`, y ningún script lo imprime. Ver `docs/seguridad_y_evidencia.md`.
