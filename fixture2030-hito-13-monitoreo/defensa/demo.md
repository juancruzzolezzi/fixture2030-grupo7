# Demostración

Está pensada para ser corta y repetible, no para ejecutar todo. Cada paso se vincula con una decisión
de base. Las variables de abajo son para copiar; `F2030-006` es ARG vs ESP, el partido de laboratorio.

## Preparación (10 minutos antes)

```bash
cd fixture2030-hito-10-api-integrada && docker compose up -d && bash scripts/redis/sembrar.sh
bash scripts/iniciar_api.sh                       # en su propia terminal
cd ../fixture2030-hito-13-monitoreo && bash scripts/iniciar_monitoreo.sh
../fixture2030-hito-10-api-integrada/.venv/bin/python scripts/verificar_targets.py   # Windows: .venv/Scripts/python.exe
```

Pestañas: Grafana, Prometheus `/targets`, Swagger (`http://localhost:8000/docs`), `defensa/presentacion.html`.
Las mismas requests están en Postman: `fixture2030-hito-10-api-integrada/postman/fixture2030_collection.json`.

## Flujo 1: comentarios y por qué Cassandra (2 min)

```bash
curl -s "http://localhost:8000/partidos/F2030-006/comentarios?bloque_horario=203006181800&limite=3"
curl -s -i "http://localhost:8000/partidos/F2030-006/comentarios?limite=3" | head -1      # sin bloque: 422, no se puede
docker exec h10-cassandra cqlsh -e "DESCRIBE TABLE fixture2030.comentarios_por_bloque" | head -14
```

**Qué demuestra**: la consulta exige partido y bloque porque la partición es esa. No existe "todos los
comentarios": es el precio de poder repartir la escritura.

## Flujo 2: partido y eventos, y por qué Neo4j (2 min)

```bash
curl -s http://localhost:8000/partidos/F2030-006/eventos
```

En Neo4j Browser (`http://localhost:7474`, sin mostrar la password):

```cypher
MATCH (p:Partido {codigo: 'F2030-006'})<-[:OCURRE_EN]-(ev:Evento)<-[:PROTAGONIZA]-(j:Jugador)
RETURN ev.tipo, ev.minuto, j.apellido
```

**Qué demuestra**: dos relaciones seguidas, sin uniones. Comparar con el flujo 1: mismo recurso "partido",
distinta base, distinto patrón.

## Otros, si preguntan

```bash
docker exec h10-redis redis-cli TTL fixture2030:sesion:user-00001        # la sesión vence sola
curl -s -X PATCH http://localhost:8000/partidos/F2030-001/estado -H 'content-type: application/json' -d '{"nuevo_estado":"EnJuego"}'    # F2030-001 está Finalizado: 409 de IRIS, no cambia nada
curl -s "http://localhost:8000/partidos/F2030-006/estadisticas?equipo_id=ARG&desde=2030-06-18T18:00:00Z&hasta=2030-06-18T18:00:05Z"     # ventana temporal
curl -s "http://localhost:8000/salud?forzar=true"                        # estado de las seis
```

Una transición válida modifica datos: en la demo usar solo esta, que es ilegal.

## Evidencia: leer el panel y la falla (4 min)

La prueba completa tarda ~3 min, y la alerta necesita más de 1 min para pasar a firing: **conviene no esperarla en vivo**.

- **Recomendado**: mostrar en Grafana el rango de una prueba ya corrida (el link lo imprime el script) y
  `evidencia/prueba_de_falla.txt`. Después, en vivo, solo el corte corto:

```bash
cd ../fixture2030-hito-10-api-integrada
docker compose stop redis
curl -s -o /dev/null -w "sesion: %{http_code}\n" http://localhost:8000/sesiones/user-00001   # 503
curl -s -o /dev/null -w "equipo: %{http_code}\n" http://localhost:8000/equipos/ARG          # 200
# en Grafana, el estado de Redis pasa a CAIDA en hasta ~25 s
docker compose start redis
```

**Qué decir**: qué falló, qué siguió, qué se perdería si esto pasara en un partido (sesiones, no datos del
torneo), y qué haríamos con esa señal.

**Opcional, si sobra tiempo o lo preguntan** (fuera del tiempo de la defensa): repetir el hallazgo del Hito 12 en
el panel. Arrancar la API con `INFLUX_REUSAR_CLIENTE=0`, correr `generar_carga.py --usuarios 30 --duracion 120`, y
comparar con `=1`. El efecto depende de la máquina: en Windows crear un cliente costaba ~250 ms.

## Plan B (RNF7)

| Si falla | Qué hacemos |
|---|---|
| Una base no levanta | Decirlo y mostrar el panel en estado degradado: es justamente lo que defendemos. Seguir con otra base. |
| Grafana o Prometheus no levantan | Capturas de `evidencia/dashboards/` y salidas `.txt`. |
| Docker o la notebook | Presentación local y capturas desde otra máquina. Tener una copia del repositorio en un pendrive. |
| Sin internet | Nada de la demo lo necesita si las imágenes ya están descargadas. La presentación no usa recursos externos. |
| Se pasa el tiempo | Cortar según `guion_de_20_minutos.md`. |

Antes de irse: `docker compose start redis` si quedó detenida, y no correr `down -v` en el Hito 10.
