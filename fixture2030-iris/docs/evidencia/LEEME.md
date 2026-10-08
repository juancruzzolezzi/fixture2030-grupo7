# Evidencia de ejecución

Corrida real sobre InterSystems IRIS Community en Docker Desktop (Windows), 08/10/2026.

## Salidas completas (texto)

| Archivo | Generado por |
|---|---|
| `salida_compilacion.txt` | `scripts/compilar.txt` (`LoadDir` de las 7 clases) |
| `salida_demo_completa.txt` | `scripts/demo.txt` (`Do ##class(Fixture.Demo).Ejecutar()`): 26 verificaciones, todas `(esperado)` |
| `salida_bloques_mac.txt` | `scripts/demo_crud_iris_fixture2030.mac` ejecutado en orden |

## Capturas del Terminal

Cada captura corre un archivo de `scripts/capturas/` con
`docker exec -i fixture2030-iris sh -c "iris session IRIS -U USER < /scripts/capturas/<archivo>.txt"`.

| Captura | Qué muestra | Requisito |
|---|---|---|
| `01_contenedor.png` | Contenedor `healthy`, puertos y volumen Durable | RF1, RNF1 |
| `02_compilacion.png` | Compilación de las 7 clases y las 6 tablas SQL | RNF2, RNF4 |
| `03_herencia_arbol_padre_hijo.png` | Secciones 1 y 2: herencia y árbol guardado con un solo `%Save` | RF3, RF4, RF6 |
| `04_falla_required_y_atomicidad.png` | Secciones 3 y 4: rechazo por `[Required]` y tipos; un hijo inválido cancela el árbol | RF5, RF6 |
| `05_maquina_estados_y_eventos_ilegales.png` | Secciones 5 y 6: transiciones ilegales y evento en el minuto 0 | RF9 |
| `06_inalterabilidad_y_navegacion.png` | Secciones 7 y 8: eventos inalterables y navegación sin SQL | RF7, RF9 |
| `07_proyeccion_sql.png` | Sección 9: los mismos objetos como tablas SQL | RF8 |
| `08_integridad_al_borrar.png` | Sección 10: borrado rechazado y borrado en cascada | Matriz de integridad |

Para regenerar todo: comandos de la sección 3 del README.
