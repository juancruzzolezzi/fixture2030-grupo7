# Evidencia de ejecución

Los archivos `01_compilacion.txt`, `02_demo_completa.txt` y `03_demo_bloques_mac.txt` salen
de una corrida real (Docker Desktop en Windows, 08/10/2026). Para regenerarlos en
Windows usar los comandos de la sección 3 del README; en Linux/macOS/WSL:

1. `docker compose up -d` y esperar `healthy` en `docker compose ps`.
2. `./scripts/cargar.sh` → captura de la compilación (la salida lista las clases
   compiladas y termina sin errores).
3. `./scripts/demo.sh` → genera `docs/evidencia/02_demo_completa.txt`. Revisar que todas las
   líneas digan `(esperado)` y ninguna `(INESPERADO!)`.
4. Capturas de pantalla del Terminal para la entrega:
   - sección 2 (árbol guardado con un solo `%Save`, IDs `1||1`, `1||2`);
   - sección 3 (rechazo por `[Required]`);
   - secciones 5 y 6 (transiciones ilegales rechazadas);
   - sección 9 (tablas SQL con los mismos datos).
5. Opcional: en el Portal de Administración (http://localhost:52773/csp/sys/UtilHome.csp,
   usuario `_SYSTEM` / `SYS`, pide cambiarla la primera vez) → System Explorer → SQL,
   namespace USER, correr `SELECT * FROM Fixture.Evento` y capturar.
