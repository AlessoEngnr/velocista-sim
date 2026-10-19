# Quickstart: validar el panel de laboratorio

Guía para comprobar de punta a punta que el panel funciona. Detalles de diseño en
[plan.md](./plan.md), [data-model.md](./data-model.md) y [contracts/](./contracts/).

## Requisitos

- `uv` y Python 3.12 (como el resto del repo).
- Para los tests de navegador, Chromium de Playwright (una sola vez por equipo):

  ```powershell
  uv sync
  uv run playwright install chromium
  ```

  En Linux/CI: `uv run playwright install --with-deps chromium`.

## 1. Tests automáticos

```powershell
uv run pytest                                      # todo (incluye tests de navegador si Chromium está instalado)
uv run pytest tests/integration/test_panel_static.py  # `/` sirve la página; /health y /ws intactos
uv run pytest -m browser                           # solo Playwright
uv run pytest -m slow tests/browser/test_panel_load.py  # carga: 30 s a 100 Hz (no corre en CI)
```

Resultado esperado:

- `test_panel_static.py`: `GET /` → 200 `text/html` con el panel; cada `.js` con
  `text/javascript`; `/health` y `/ws` como antes; ningún recurso apunta a otro origen.
- `tests/browser/test_panel_smoke.py`: abre el panel contra un `uvicorn` local, ve `CONECTADO` y
  los datos de `hello`, pulsa **Iniciar**, ve `EN CORRIDA` y que `seq` avanza; todo frame enviado
  valida con `validate_command` y todo frame recibido con `validate_message`.
- `tests/browser/test_panel_commands.py`: los 9 constructores de `commands.js` producen comandos
  válidos (FR-037).
- `tests/browser/test_panel_robot.py`: con un "robot real" simulado (`route_web_socket`), sin
  errores de consola y con los controles solo-sim ocultos (SC-006).
- `tests/browser/test_panel_load.py` (marcadores `browser` y `slow`, excluido de `uv run pytest`
  y de la CI por `-m 'not slow'`): 30 s de corrida a 100 Hz con `seq-lost == 0` y controles que
  siguen respondiendo (SC-003, versión corta).

Si Chromium no está instalado, los tests `browser` aparecen como **omitidos** con el comando de
instalación en el motivo. En la CI (`VELOCISTA_REQUIRE_BROWSER=1`) eso es un fallo.

## 2. Prueba manual en local

```powershell
uv run velocista-sim        # http://localhost:8000/
```

Abrir `http://localhost:8000/` en el navegador (ventana de 1440 × 900 o mayor).

| # | Acción | Resultado esperado | Requisitos |
|---|---|---|---|
| 1 | Abrir la página | `● CONECTADO`; robot `velocista-01`, `source sim`; `config` con `kp 0.0450`, `kd 0.9000`, `base_speed 180`, `50 Hz`, pista `oval-01`; regleta de 16 barras moviéndose; `SIN CORRIDA` | US1-1, US1-2 |
| 2 | Pulsar **Iniciar** | el rastro anterior se borra; `EN CORRIDA` con `run_id`; el rastro se dibuja en magenta; tras unos segundos aparece la vuelta 1 en el historial | US1-3, US1-4 |
| 2b | Pulsar **Limpiar rastro** | el rastro se vacía y vuelve a dibujarse desde la posición actual; no se envía ningún comando | FR-018 |
| 3 | Pulsar **Detener** | resumen arriba en Corridas con vueltas, mejor/promedio, salidas, pista, config y `config_changed` | US1-5 |
| 4 | Vueltas objetivo = 2, Iniciar | al completar la vuelta 2 la corrida termina sola (un único `stop` en el registro) | US1-7, FR-045 |
| 5 | Arrastrar `kp` durante una corrida | los valores confirmados se actualizan en < 1 s; al detener, `config_changed = sí` | US2, SC-002 |
| 6 | Escribir `kp = -1` | campo marcado inválido, no se envía nada | FR-011 |
| 7 | Frecuencia = 150 | campo inválido; con 100, la telemetría pasa a 100 Hz (el `seq` avanza más rápido) y el panel sigue fluido | US2-5, SC-003 |
| 8 | `base_speed` = 255 y `kp` alto hasta que el robot se salga | `✕ FUERA DE PISTA (line_lost)` en el registro y luego el resumen | US1-6 |
| 9 | Pestaña Robot y pista → elegir `velocista-01` | nuevo `hello`/`config`, rastro limpio, calibración "por defecto" | US3-2 |
| 10 | Elegir la pista `oval-01` del catálogo y confirmar | reconexión con `?track=oval-01&robot=velocista-01`, sesión nueva | US3-3 |
| 11 | Cargar `config/tracks/oval-01.json` como archivo | `config` con su `track_id`, rastro limpio | US3-4 |
| 12 | Cargar un `.txt` cualquiera | error local "el archivo no es JSON válido", nada enviado | US3-5 |
| 13 | Cargar como archivo el objeto `message` de `contract/examples/invalid/track/gaps-overlap.json`, guardado aparte (el archivo completo es un envoltorio de ejemplo, no una pista) | `invalid_track` visible; la pista no cambia | US3-6 |
| 14 | Calibración: `wheelbase_m = 0.128`, Aplicar | `MEDIDO 0.128 m`; luego Borrar → `POR DEFECTO` | US4-2, US4-3 |
| 15 | Calibración: `adc_noise = -5`, Aplicar | campo marcado inválido, no se envía nada (fuera del rango del contrato); ninguna marca cambia | FR-030, FR-037 |
| 16 | Durante una corrida, abrir Robot y pista o Calibración | acciones deshabilitadas con "Detén la corrida para cambiar esto" | US3-7, US4-7 |
| 17 | Cortar el servidor (Ctrl+C) | `DESCONECTADO` y botón Reconectar; los controles se deshabilitan | US1-10 |
| 18 | `VELOCISTA_MAX_SESSIONS=1`, abrir dos pestañas | la segunda muestra "Servidor lleno" y permite reintentar | borde "servidor lleno" |
| 19 | Revisión visual lado a lado con `docs/design/reference.png` | misma paleta, acento magenta, rótulos en mayúsculas tenues, tres columnas; sin imágenes, degradados ni animaciones; números monoespaciados que no "saltan" | SC-009, SC-010 |
| 20 | **Antes de abrir el PR**: frecuencia = 100 Hz, Iniciar y dejar correr **5 minutos** (vueltas objetivo vacío); mover `kp` y `base_speed` al final | `seq-lost` sigue en 0, el rastro se dibuja sin cortes, los sliders y Detener responden sin trabas y el `config` se confirma en < 1 s | SC-003 |

## 3. En Railway

Tras el despliegue, abrir `https://<proyecto>.up.railway.app/`: el panel debe conectarse por
`wss` (pestaña Red del navegador → `/ws` con esquema `wss`) y repetir los pasos 1–3.
