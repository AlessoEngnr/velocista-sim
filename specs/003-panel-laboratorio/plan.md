# Implementation Plan: Panel de laboratorio web para el simulador

**Branch**: `003-panel-laboratorio` | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)

**Input**: Especificación de la feature en `specs/003-panel-laboratorio/spec.md`

## Summary

Página estática (HTML, CSS y JavaScript con módulos ES nativos, sin frameworks ni paso de build)
en `src/velocista_sim/server/static/`, que el mismo servicio FastAPI entrega en `/` con
`StaticFiles` montado después de `/health` y `/ws`. La página abre su propia sesión en `/ws` del
mismo origen (`ws`/`wss` según la página) y usa **solo** mensajes y comandos del contrato v1: es
un cliente más y el ejemplo de referencia del front. El estado de la sesión vive en memoria en un
único módulo (`state.js`, `applyMessage` por `type`), los comandos se construyen en
`commands.js` (una función por comando, validadas en los tests) y el dibujo se hace a lo sumo una
vez por cuadro con Canvas 2D (regleta y rastro de `sim_truth`). Estilo de instrumentación oscura
tomado de `docs/design/reference.png` (paleta, acento magenta, rótulos en mayúsculas tenues,
grilla de tres columnas), con números en monoespaciada del sistema. Tests: `/` sirve la página sin
romper `/health` ni `/ws`, y pruebas de humo con Playwright (dependencia solo de desarrollo)
contra un `uvicorn` local que hacen `start` y ven llegar telemetría.

## Technical Context

**Language/Version**: Python 3.12 (servidor, sin cambios de versión); HTML5, CSS y JavaScript
ES2022 con módulos nativos para el navegador.

**Primary Dependencies**: servidor: FastAPI/Starlette ya presentes (`StaticFiles`, sin
`aiofiles`, research R1) — **ninguna dependencia nueva de ejecución**. Navegador: ninguna (sin
frameworks, sin npm, sin CDN). Dev: **playwright** (nueva, `uv add --dev playwright`; pruebas
de navegador, research R12) más los navegadores instalados con `uv run playwright install
chromium`.

**Storage**: N/A. Estado solo en memoria de la pestaña (FR-036); archivos estáticos de solo
lectura dentro del paquete.

**Testing**: pytest. `fastapi.testclient.TestClient` para `/`, MIME de los recursos y no
regresión de `/health` y `/ws`. Playwright (API síncrona de Python, Chromium headless) contra un
`uvicorn` real en un hilo (fixture compartido `tests/support/live_server.py`), marcador `browser`;
se omiten si falta Chromium salvo con `VELOCISTA_REQUIRE_BROWSER=1` (CI). Los frames WS enviados y
recibidos se validan con `validate_command` / `validate_message` (principio VII).

**Target Platform**: navegadores de escritorio actuales (Chromium, Firefox, Safari) servidos por
el contenedor de Railway; desarrollo local en Windows/Linux.

**Project Type**: web-service existente + cliente web estático servido por el mismo servicio.

**Performance Goals**: telemetría hasta 100 Hz durante 5 min sin trabas (SC-003): mensajes
aplicados al llegar, render coalescido en `requestAnimationFrame`; confirmación de `set_config`
visible en < 1 s (SC-002).

**Constraints**: solo contrato v1 (FR-003); sin pedidos a otros orígenes; sin animaciones ni
imágenes (FR-043); contraste AA (SC-011); vista principal sin desplazamiento en 1440 × 900
(FR-044); textos en español (FR-034); topes: rastro 5 000 puntos, vueltas 100, resúmenes 50,
registro 50.

**Scale/Scope**: una página, ~10 tarjetas/vistas, ~15 módulos JS chicos; una sesión WS por
pestaña (cuenta para `max_sessions` del servidor como cualquier cliente).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Cómo se cumple | Estado |
|---|---|---|
| I. Contrato fuente de verdad | El panel no agrega mensajes, campos, comandos, parámetros de conexión ni canales: usa `/ws` con `track`/`robot` y los 9 comandos v1. La ruta HTTP `/` no es interfaz de datos (como `/health`) y no requiere cambio de contrato. Unidades del contrato; los tiempos se muestran en `s` (SI) y nunca en km/h u otras (R10). | ✅ |
| II. Paridad sim–robot | Las vistas y controles solo-sim (`sim_truth`, `reset`, `load`, `set_profile`, `load_track`) dependen de `hello.source`; con `source = "robot"` se ocultan y el resto funciona igual (FR-035). Batería y vueltas dependen de `capabilities`. Un test con un robot real simulado lo verifica (R14). | ✅ |
| III. El robot no conoce la pista | No se toca `world` ni `robot`. El panel no recibe geometría de pista (no viaja por el contrato) y solo dibuja `sim_truth`, que es el canal solo-sim previsto para la verdad del mundo. | ✅ |
| IV. Control a bordo | El panel solo configura (`set_config`, `set_rate`, …) y observa. El throttle de sliders (≤ 5/s) cambia parámetros, no es un lazo de control. El `stop` automático de vueltas objetivo es una orden de corrida, como el botón Detener. | ✅ |
| V. Perfil default/measured | `set_profile` fija o borra (`null`) valores medidos; el panel marca "medido"/"por defecto" según respuestas aceptadas. No se modifica el servidor, que ya registra el perfil efectivo. | ✅ |
| VI. Simulación reproducible | Sin cambios en la simulación; el panel no lee ni altera el ritmo ni la semilla. | ✅ |
| VII. Validación contra JSON Schema | Todo comando que el panel puede construir se valida con `validate_command` (R13), y en el test de humo todo frame enviado y recibido se valida con el contrato. Los mensajes del robot falso de R14 se validan antes de enviarlos. | ✅ |
| Restricciones técnicas | Python 3.12, `uv add --dev playwright` (justificada: el usuario pidió test de humo con Playwright; no llega a la imagen), código en `src/velocista_sim/`, tests en `tests/`. El JavaScript no es código Python ni requiere toolchain: no añade dependencias de ejecución. | ✅ |
| Flujo de desarrollo | Identificadores en inglés (archivos, funciones y variables JS, `data-testid`); textos visibles, comentarios y docstrings en español; nombres del contrato tal cual; Conventional Commits. | ✅ |

Sin violaciones.

**Re-check post-diseño (Phase 1)**: [data-model.md](./data-model.md) y
[contracts/](./contracts/) mantienen los nueve puntos. Observaciones: (a) la cola FIFO de
pendientes (R5), solo con los comandos que responden `config`, atribuye respuestas usando el
orden que el contrato ya garantiza y el `cmd` de `error`, sin ids nuevos; (b) cambiar de pista del catálogo se hace con una sesión nueva y los parámetros de
conexión del contrato, como asume la spec, sin ampliar v1; (c) `contracts/http-panel.md` deja
explícito que `/` y sus recursos no son parte del contrato v1.

## Project Structure

### Documentation (this feature)

```text
specs/003-panel-laboratorio/
├── plan.md              # Este archivo
├── research.md          # Phase 0: decisiones R1–R16
├── data-model.md        # Phase 1: estado del panel en el navegador
├── quickstart.md        # Phase 1: validación automática y manual
├── contracts/
│   ├── http-panel.md        # GET / y recursos estáticos; /health y /ws intactos
│   ├── client-protocol.md   # qué mensajes/comandos v1 usa el panel y cuándo
│   └── ui-hooks.md          # distribución y anclas data-testid para los tests
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks; no lo crea este comando)
```

### Source Code (repository root)

```text
src/velocista_sim/server/
├── app.py                    # + mimetypes .js/.css y app.mount("/", StaticFiles(..., html=True)) al final
└── static/                   # NUEVO: panel servido en /
    ├── index.html            # estructura: barra superior + 3 columnas de tarjetas (ui-hooks.md)
    ├── panel.css             # tokens de color/tipografía (R11), grilla, componentes
    └── js/
        ├── main.js           # arranque: crea el estado, conecta, enlaza eventos de UI y el bucle rAF
        ├── connection.js     # URL ws/wss del mismo origen, abrir/cerrar, send(), códigos de cierre
        ├── commands.js       # una función pura por comando v1 (FR-037)
        ├── state.js          # PanelState y applyMessage(state, message) por type; cola de pendientes
        ├── trail.js          # buffer circular de 5 000 puntos y caja envolvente
        ├── format.js         # formato fijo de cada magnitud con unidad (R10)
        ├── profile-params.js # metadatos de los 12 parámetros de set_profile
        ├── throttle.js       # throttle con envío final garantizado (R8)
        └── views/
            ├── topbar.js         # estado de conexión, métricas en línea, robot
            ├── sensors.js        # canvas de la regleta + line_position/error/line_lost
            ├── controller.js     # términos PID y PWM de motores
            ├── trail-view.js     # canvas del rastro + franja de valores + botón Limpiar rastro
            ├── control.js        # botones, vueltas objetivo, sliders y campos, pestañas
            ├── robot-track.js    # catálogo, load, cambio de pista, load_track desde archivo
            ├── calibration.js    # 12 parámetros, aplicar/borrar, estado medido/por defecto
            ├── laps.js           # vuelta actual, última, mejor, promedio, historial
            ├── runs.js           # resúmenes de corridas
            └── log.js            # registro de eventos y errores

tests/
├── support/
│   └── live_server.py        # NUEVO: uvicorn real en hilo y puerto libre (extraído de test_health_client.py)
├── integration/
│   ├── test_health_client.py # usa el fixture compartido
│   └── test_panel_static.py  # NUEVO: / sirve la página, MIME, sin orígenes externos, /health y /ws intactos
└── browser/                  # NUEVO, marcador `browser`
    ├── conftest.py           # Chromium headless; omitir/fallar según VELOCISTA_REQUIRE_BROWSER; captura de frames WS
    ├── test_panel_smoke.py   # abre /, ve CONECTADO, start → EN CORRIDA y seq avanzando; valida frames
    ├── test_panel_commands.py# los 9 constructores de commands.js validan contra el contrato
    └── test_panel_robot.py   # robot real simulado con route_web_socket (SC-006)

pyproject.toml                # + playwright en [dependency-groups].dev; + marcador "browser"
.github/workflows/tests.yml   # + `uv run playwright install --with-deps chromium`; VELOCISTA_REQUIRE_BROWSER=1
README.md                     # + sección "Panel de laboratorio" (abrir /, instalar Chromium para tests)
```

Proyecto único existente. El panel vive dentro del paquete del servidor
(`server/static/`) para que el `Dockerfile` (que copia `src/`) y el wheel lo incluyan sin
cambios, y se sirve con el mismo proceso. Los tests de navegador van en `tests/browser/` con su
propio `conftest.py` para aislar la dependencia de Chromium; el servidor real en hilo se comparte
desde `tests/support/`. No se modifica `contract/`, `world/`, `robot/` ni la lógica de sesión.
