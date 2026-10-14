# Evidencia

Todo lo que hay acá salió de correr la API real contra las 6 bases
levantadas por `docker-compose.yml`, el 14/10/2026.

- `salud.txt`: `GET /salud`, conectividad real a las 6 fuentes.
- `pytest.txt`: las 22 pruebas de integración (`tests/integration/`),
  incluida la que para y levanta Redis de verdad.
- `api_server.log`: log de la aplicación filtrado a las líneas de request
  (`request_id`, método, ruta, status, duración) — evidencia de que cada
  uno de los 14 endpoints efectivamente llegó a su fuente y devolvió una
  respuesta compatible con el contrato (RF17), y la base del mecanismo de
  correlación de RF18/RNF10.
- `latencia.txt`: medición de latencia básica (RNF18) para un endpoint de
  cada tipo de driver (nativo TCP vs. HTTP+SQL).

Si alguien vuelve a correr todo desde cero, estos archivos se pisan con la
salida de esa corrida nueva.
