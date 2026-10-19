---

description: "Lista de tareas para implementar el panel de laboratorio web"
---

# Tasks: Panel de laboratorio web para el simulador

**Input**: documentos de diseño en `specs/003-panel-laboratorio/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: SÍ se incluyen. La spec (FR-037, SC-004, SC-006) y el plan piden explícitamente: test de
`/` y no regresión de `/health` y `/ws`, validación de los 9 comandos de `commands.js` contra el
contrato, test de humo con Playwright y test de robot real simulado.

**Organization**: tareas agrupadas por historia de usuario para implementar y probar cada una por
separado.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: puede hacerse en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia de usuario a la que pertenece (US1, US2, US3, US4)
- Rutas relativas a la raíz del repo. Todos los archivos del panel están en
  `src/velocista_sim/server/static/` (abreviado `static/` en el texto solo cuando la ruta completa
  ya se dio en la misma tarea).

## Convenciones para todas las tareas

- Identificadores (archivos, funciones, variables JS, `data-testid`) en inglés; textos visibles,
  comentarios y docstrings en español (constitución, FR-034).
- Sin frameworks, sin npm, sin CDN, sin fuentes externas: solo módulos ES nativos (research R3,
  R11). Ningún archivo estático contiene `ws://` ni `wss://` literales, ni ninguna URL
  `http://`/`https://` (ni en comentarios) salvo espacios de nombres `http://www.w3.org/`
  (contracts/http-panel.md).
- Los `data-testid` son los de [contracts/ui-hooks.md](./contracts/ui-hooks.md) y no se renombran.
- Todo número visible se formatea con `static/js/format.js` (research R10); `null`/ausente → `—`.
- Ningún comando se construye fuera de `static/js/commands.js` (research R13).
- Commits en Conventional Commits con descripción en español (p. ej. `feat(panel): …`).

---

## Phase 1: Setup (infraestructura compartida)

**Purpose**: dependencias de desarrollo, marcador de tests, CI y estructura de carpetas.

- [X] T001 Crear la estructura vacía del panel: `src/velocista_sim/server/static/`, `src/velocista_sim/server/static/js/` y `src/velocista_sim/server/static/js/views/` (con un `index.html` mínimo provisional que diga "Panel de laboratorio" para poder montar y probar la ruta)
- [X] T002 Agregar Playwright como dependencia solo de desarrollo con `uv add --dev playwright` (actualiza `pyproject.toml` en `[dependency-groups].dev` y `uv.lock`); no tocar `[project].dependencies`
- [X] T003 [P] Registrar el marcador `browser` en `pyproject.toml` (`[tool.pytest.ini_options].markers`: `"browser: prueba de navegador con Playwright (requiere Chromium)"`), manteniendo `addopts = "-ra -m 'not slow'"` sin excluir `browser`
- [X] T004 [P] Actualizar `.github/workflows/tests.yml`: tras `uv sync --locked`, agregar el paso `uv run playwright install --with-deps chromium` y fijar `env: VELOCISTA_REQUIRE_BROWSER: "1"` en el paso `uv run pytest`

---

## Phase 2: Foundational (prerrequisitos bloqueantes)

**Purpose**: entrega de la página en `/`, esqueleto de la UI, conexión, estado base, comandos y
la infraestructura de tests de navegador. Todas las historias dependen de esta fase.

**⚠️ CRITICAL**: ninguna historia puede empezar antes de terminar esta fase.

### Servidor y tests de entrega

- [X] T005 En `src/velocista_sim/server/app.py`: definir `STATIC_DIR = Path(__file__).parent / "static"`, llamar `mimetypes.add_type("text/javascript", ".js")` y `mimetypes.add_type("text/css", ".css")` (research R2) y, **al final** de `create_app` (después de `GET /health` y `WS /ws`), `app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="panel")` (research R1); actualizar el docstring del módulo para mencionar el panel en `/`
- [X] T006 [P] Extraer `_free_port()` y el fixture `server_url` (uvicorn real en hilo y puerto libre) de `tests/integration/test_health_client.py` a `tests/support/live_server.py` como helpers reutilizables (p. ej. `start_live_server(settings=None) -> contextmanager[str]` que devuelve `http://127.0.0.1:<puerto>`), y hacer que `tests/integration/test_health_client.py` los use sin cambiar sus asserts
- [X] T007 Crear `tests/integration/test_panel_static.py` con `fastapi.testclient.TestClient`: `GET /` → 200, `content-type` empieza con `text/html` y contiene el `<title>` del panel; cada archivo bajo `src/velocista_sim/server/static/` con extensión `.js` se sirve con `text/javascript` y `.css` con `text/css` (recorriendo el directorio, no una lista fija), y el test **exige** que exista al menos `js/main.js` y `panel.css` para no pasar sin comprobar nada (si se escribe antes que T010/T017, queda en rojo hasta entonces); ruta inexistente → 404; `GET /health` y una conexión a `/ws` (recibe `hello` y `config` válidos con `validate_message`) siguen funcionando; ningún archivo de `static/` contiene `ws://` ni `wss://` literales, y toda aparición de `http://` o `https://` (incluidos comentarios) empieza con `http://www.w3.org/` (contracts/http-panel.md) (depende de T005)
- [X] T008 Crear `tests/browser/conftest.py`: aplica el marcador `browser` a todo el directorio; fixture de sesión que lanza Chromium headless con `playwright.sync_api` (sin `pytest-playwright`); si Chromium no está instalado, `pytest.skip("Falta Chromium: uv run playwright install chromium")`, salvo con `VELOCISTA_REQUIRE_BROWSER=1`, donde es `pytest.fail`; fixture `live_url` que usa `tests/support/live_server.py`; fixture `page` (viewport 1440 × 900) que captura los errores de consola y los frames WS (`page.on("websocket")` → `framesent`/`framereceived`) en listas expuestas al test, y un helper `assert_frames_valid(frames)` que valida cada enviado con `validate_command` y cada recibido con `validate_message` usando el último `hello` (research R12, principio VII) (depende de T002, T006)

### Esqueleto de la página y estilo

- [X] T009 Escribir `src/velocista_sim/server/static/index.html` completo (reemplaza el provisional de T001): `lang="es"`, `<link rel="stylesheet" href="panel.css">`, `<script type="module" src="js/main.js">`; `header.topbar` y tres columnas con **todas** las tarjetas y **todos** los `data-testid` de contracts/ui-hooks.md (Regleta, Controlador, Motores, Registro; Rastro con franja `speed`/`distance`/`pose-x`/`pose-y`/`theta` y `btn-trail-clear`; Control con `btn-start`/`btn-stop`/`btn-reset`/`lap-target-input` y pestañas `tab-tuning`/`tab-robot-track`/`tab-calibration` con `role="tablist"`/`role="tab"`/`aria-selected` y sus paneles vacíos; Vueltas; Corridas); `conn-status`, `run-status` y `line-lost` con `aria-live="polite"`; `<details>` plegado con `session-id`, capacidades, `firmware` y `hw_rev` dentro del selector de robot de la barra superior (FR-039); `btn-reconnect` oculto; rótulos en mayúsculas en español; cada campo con `<label>` asociado; sin imágenes ni íconos decorativos (FR-043)
- [X] T010 [P] Escribir `src/velocista_sim/server/static/panel.css`: tokens de research R11 en `:root` (`--bg #0b0b0e`, `--card #15151a`, `--raised #1d1d24`, `--border #26262e`, `--text #f2f2f4`, `--muted #8e8e99`, `--accent #e5336d`, `--accent-text #f0517f`, `--best #8cc4f2`, `--warn #f2b33d`, `--danger #ff6b5e`, `--ok #4fd18b`, botón primario `#c81e57`, `--font-sans` y `--font-mono` con las pilas de R11); grilla `minmax(280px, 1fr) minmax(0, 2fr) minmax(320px, 1.2fr)` con altura `100vh` y tarjetas con listas desplazables por dentro (FR-044); por debajo de ~1100 px una columna en orden Control → izquierda → centro con `order`, sin scroll horizontal; rótulos en mayúsculas pequeñas tenues con espaciado de letras (FR-041); valores en `--font-mono`, `font-variant-numeric: tabular-nums`, alineados a la derecha con `min-width` en `ch` (FR-040, SC-009); control segmentado para pestañas; estados con colores `--warn`/`--danger`/`--ok`; jerarquía (FR-039): una escala de tamaños explícita en tokens (p. ej. `--size-primary`, `--size-value`, `--size-secondary`) donde estado de corrida (`run-status`), `error`, la regleta, `pwm-left`/`pwm-right`, la vuelta actual y `lap-best` usan el tamaño mayor y `--text`, y los datos de sesión (`session-id`, capacidades, `firmware`, `hw_rev`) el menor y `--muted`; sin degradados, sombras marcadas, brillos ni `transition`/`animation` (FR-043); `[hidden]` siempre oculta
- [X] T011 [P] Escribir `src/velocista_sim/server/static/js/format.js`: una función exportada por magnitud según la tabla de research R10 (`formatError`, `formatLinePosition`, `formatAdc`, `formatPid` 1 decimal con signo, `formatPwm` entero con signo, `formatVolts` 2 decimales, `formatSpeed`, `formatDistance` 2 decimales, `formatCoord` y `formatTheta` 3 decimales con signo, `formatSeconds` de ms a s con 3 decimales, `formatHz`, `formatGain` 4 decimales); signo explícito con `+` y `−` (U+2212); `null`/`undefined` → `—`; cada función devuelve texto con la unidad del contrato (`‰ sensor`, `ADC`, `PWM`, `V`, `m/s`, `m`, `rad`, `s`, `Hz`), nunca km/h

### Conexión, comandos y estado base

- [X] T012 [P] Escribir `src/velocista_sim/server/static/js/commands.js`: una función pura exportada por comando v1, sin efectos (contracts/client-protocol.md): `start()`, `stop()`, `reset()`, `setConfig(fields)` (para `kp`/`ki`/`kd` produce `{"cmd":"set_config","params":{…}}` y para `base_speed` `{"cmd":"set_config","base_speed":n}` con `Math.round` y límite 0–255), `setRate(hz)`, `list()`, `load(robotId)`, `setProfile(measured)` (enteros donde el contrato pide enteros: `adc_white`, `adc_black`, `adc_noise`, `encoder_ticks_per_rev`; admite `null` para borrar), `loadTrack(track)`; sin `v` ni `t_ms`; comentario de cabecera en español explicando que es la única vía para construir comandos
- [X] T013 [P] Escribir `src/velocista_sim/server/static/js/connection.js`: `buildUrl({track, robot} = {})` con `ws:`/`wss:` según `location.protocol` y `new URL("/ws", …)`, agregando solo `track` y `robot` con `searchParams` cuando se pasan (research R4); `connect(url, handlers)` que abre el `WebSocket`, parsea cada frame de texto como JSON (frame no JSON → `handlers.onInvalid`), y llama `onOpen`, `onMessage(message)`, `onClose(code)`; `send(command)` que hace `JSON.stringify` solo si el socket está `OPEN` (si no, no envía nada); `close()`; sin reconexión automática (research R15)
- [X] T014 Escribir `src/velocista_sim/server/static/js/state.js` (base): `createState()` con la forma de `PanelState` de data-model.md (`connection {status, url, closeCode, sessionId}`, `hello`, `config`, `catalog`, `pending`, `telemetry {last, lastSeq, lost, received}`, `run`, `trail`, `lapTarget {value, stopSentFor}`, `calibration`, `summaries`, `log`, `drafts`, más `dirty`); `derived(state)` con `isSim`, `sensorCount`, `adcMax = 2 ** adc_bits − 1`, `hasBattery = capabilities.battery.voltage_sense`, `hasLaps = capabilities.lap_timing`; `applyMessage(state, message)` con un `switch` por `type` que en esta fase implementa `hello` (reemplaza, recalcula derivados), `config` (reemplaza; resuelve como aceptado el pendiente **más antiguo** y devuelve el pendiente resuelto), `catalog` (reemplaza), `error` (agrega entrada al `log`; resuelve como rechazado el pendiente más antiguo cuyo `cmd` coincida con `error.cmd`; si ninguno coincide o no hay `cmd`, la cola no cambia) y `default` (registra `warning`, no rompe); `enqueuePending(state, command)` solo para `set_config`, `set_rate`, `set_profile`, `load`, `load_track` (research R5); `addLog(state, entry)` con tope **50**, el más reciente primero, `kind` ∈ `"event" | "error" | "local" | "warning"`; `resetSession(state)` que se llama al reconectar (botón Reconectar o cambio de pista) y reinicia todo el estado **menos `log`**: `hello`, `config`, `catalog`, cola de pendientes, `telemetry` (`last`, `lastSeq`, `lost`, `received`), `run`, rastro, `lapTarget.stopSentFor`, calibración y **`summaries` (los resúmenes se borran al reconectar)**; el registro de eventos y errores se conserva hasta recargar la página (research R15) (depende de T012)
- [X] T015 [P] Escribir `src/velocista_sim/server/static/js/views/log.js`: `renderLog(root, state)` que dibuja `[data-testid=log]` como `li` con `data-kind`, tiempo (`formatSeconds(tMs)`) y texto; `code` de error desconocido mostrado como error genérico con su `message`; errores con `code · cmd · message` en `--danger` y con símbolo `✕` (no solo color, FR-042)
- [X] T016 [P] Escribir `src/velocista_sim/server/static/js/views/topbar.js` (base): `renderTopbar(root, state)` para `conn-status` (`CONECTANDO`/`● CONECTADO`/`DESCONECTADO` con `data-state` `connecting`/`open`/`closed`), `btn-reconnect` visible solo con `closed`, mensaje de cierre según `closeCode` (1013 → "Servidor lleno: no se pudo abrir la sesión. Reintentar más tarde"; 1008 → "El servidor cerró la sesión porque el panel no leía a tiempo"), `robot-id`, `source`, `session-id`, `firmware`, `hw_rev` y capacidades en el `<details>`, `rate-hz` y `track-id` del último `config`; escribir `textContent` solo si cambió
- [X] T017 Escribir `src/velocista_sim/server/static/js/main.js` (base): crea el estado, conecta con `connection.js`, en cada mensaje llama `applyMessage` y marca `dirty`; tras el **primer** `config` de cada sesión envía `commands.list()`; bucle `requestAnimationFrame` que llama a las vistas solo si `dirty` (research R6); `sendCommand(command)` central que envía, encola en pendientes cuando corresponde y registra; con `status !== "open"` deshabilita todos los controles; `btn-reconnect` llama `resetSession` y reconecta; frames no JSON → `warning` en el registro (depende de T013, T014, T015, T016)
- [X] T018 Crear `tests/browser/test_panel_commands.py`: abre `/`, ejecuta en la página `await import("/js/commands.js")`, construye ejemplos de los 9 comandos (incluidos `setConfig` con `kp`, `ki`, `kd` y `base_speed` por separado, `setRate(10)` y `setRate(100)`, `setProfile` con un valor, con un entero y con `null`, y `loadTrack` con el contenido de `config/tracks/oval-01.json`) y valida cada uno en Python con `validate_command`; falla si `commands.js` exporta una función sin caso de prueba (compara `Object.keys(module)` con los casos) (FR-037, research R13) (depende de T008, T012)

**Checkpoint**: `/` sirve el panel, se ve `● CONECTADO` con datos de `hello`/`config`, `/health` y `/ws` siguen pasando sus tests, y los 9 comandos validan contra el contrato.

---

## Phase 3: User Story 1 - Ver la simulación en vivo y controlar corridas (Priority: P1) 🎯 MVP

**Goal**: ver telemetría, eventos, rastro, vueltas y resúmenes, y controlar corridas con
Iniciar/Detener/Reiniciar y vueltas objetivo; funciona igual con un robot real (sin elementos
solo-sim).

**Independent Test**: con `uv run velocista-sim`, abrir `/`, ver `● CONECTADO` y los datos de
`hello`/`config`, pulsar Iniciar, ver la regleta/PID/motores/rastro actualizándose y al menos una
vuelta, pulsar Detener y ver el resumen (quickstart pasos 1–4, 8, 17).

### Tests for User Story 1 ⚠️

> Escribirlos primero y comprobar que fallan antes de implementar.

- [X] T019 [P] [US1] Agregar a `tests/browser/test_panel_smoke.py` (creado antes de la Fase 3 con la prueba de humo de conexión y la de errores en el registro) el test de corrida: abre `live_url`, espera `conn-status` con `data-state="open"` y `robot-id` = `velocista-01`, `run-status` `data-state="idle"`; pulsa `btn-start`, espera `run-status` `data-state="running"` y `run-id` no vacío; comprueba que `seq` aumenta entre dos lecturas y que `trail-canvas` tiene `data-points` > 0; pulsa `btn-stop` y espera un `li` en `summaries`; ya sin corrida, pulsa `btn-reset` y comprueba que se envió `{"cmd":"reset"}` y que `trail-canvas` queda con `data-points="0"` (US1-8); al final, `assert_frames_valid` sobre todos los frames y ninguna entrada en los errores de consola
- [X] T020 [P] [US1] Crear `tests/browser/test_panel_robot.py`: con `page.route_web_socket("**/ws", handler)` simula un robot real que envía `hello` con `source="robot"`, `lap_timing=false`, `battery.voltage_sense=false`, `config` con `track_id=null` y telemetría sin `sim_truth`/`lap`/`battery_v` (cada mensaje validado con `validate_message` antes de enviarlo); verifica que no hay errores de consola, que `btn-reset`, `tab-robot-track`, `tab-calibration`, la tarjeta Rastro, `battery`, `lap-target-input` y la tarjeta Vueltas están ocultos, que la regleta y el PID muestran valores y que `btn-start` envía `{"cmd":"start"}`; además el robot falso envía telemetrías con un salto de `seq` (p. ej. 1, 2, 3, 7) y el test verifica `seq` = 7 y `seq-lost` = 3 (FR-019) (SC-006, FR-035, research R14)
- [X] T021 [US1] Agregar a `tests/browser/test_panel_smoke.py` un test de vueltas objetivo con `route_web_socket` (servidor falso que valida cada mensaje con `validate_message`): objetivo 2 → tras `event lap` n=2 y varias telemetrías con `lap.n=2` el panel envía exactamente **un** `stop`; campo vacío → nunca envía `stop` por su cuenta; valor `0` o `1.5` → `lap-target-input` con `aria-invalid="true"` y sin efecto (FR-045, research R16). En el mismo archivo, un test de desconexión con servidor falso: (a) tras `hello`+`config` el servidor cierra la conexión → `conn-status` con `data-state="closed"` y texto `DESCONECTADO`, `btn-reconnect` visible y `btn-start`, `kp-input` y `rate-input` deshabilitados; (b) el servidor cierra con código 1013 al abrir → se ve el mensaje "Servidor lleno" y `btn-reconnect`; pulsar `btn-reconnect` abre un WebSocket nuevo a `/ws` (US1-10, FR-004, borde "servidor lleno", research R15)

### Implementation for User Story 1

- [X] T022 [P] [US1] Escribir `src/velocista_sim/server/static/js/trail.js`: `createTrail(capacity = 5000)` con dos `Float32Array` (`xs`, `ys`), `start`, `length`, `bounds {minX, maxX, minY, maxY}` y `pose {x, y, theta} | null`; `pushPoint(trail, x, y, theta)` como buffer circular que sobrescribe el más antiguo y recalcula `bounds` al sobrescribir; `clearTrail(trail)`; `forEachPoint(trail, fn)` del más antiguo al más reciente (data-model.md, Trail)
- [X] T023 [US1] Extender `applyMessage` en `src/velocista_sim/server/static/js/state.js` para `telemetry`: guardar `last`, sumar `seq − lastSeq − 1` a `lost` cuando es > 0, actualizar `lastSeq` y `received` (FR-019); con `sim_truth` agregar el punto al rastro con `pushPoint`; estado de corrida desde `telemetry.running`/`run_id`: si llega `running=true` con un `run_id` distinto del de `run` (o sin `run`) y no hubo `run_started`, crear `run` con ese `runId` y `laps` vacío, igual que `run_started` (data-model.md, ObservedRun); si `running=false` sin `run_finished`, volver a "sin corrida" sin resumen; y para `event`: `run_started` crea `run {runId, laps: [], bestLapMs, lastLapMs, avgLapMs, offTracks: []}`; `lap` antepone `{n, lapMs}` (tope **100**) y recalcula última/mejor/promedio; `off_track` agrega `{tMs, reason}` y registra `✕ FUERA DE PISTA (<reason>)`; `run_finished` antepone `{run_id, t_ms, ...summary}` a `summaries` (tope **50**) y deja `run = null`; cada evento se registra en el `log` con su `t_ms`; un `hello` nuevo limpia el rastro y `resetSession` reinicia `lastSeq`/`lost` (depende de T022)
- [X] T024 [US1] Implementar vueltas objetivo en `src/velocista_sim/server/static/js/state.js`: `setLapTarget(state, text)` acepta vacío (`null`) o entero ≥ 1 y devuelve si es válido (inválido no cambia `lapTarget.value`); `shouldAutoStop(state)` devuelve `true` si hay corrida, `lapTarget.value !== null`, vueltas completadas (`event lap` / `telemetry.lap.n`) ≥ objetivo y `stopSentFor !== run.runId`; `markAutoStop(state)` guarda `stopSentFor = run.runId` (research R16)
- [X] T025 [P] [US1] Escribir `src/velocista_sim/server/static/js/views/sensors.js`: canvas `sensors-canvas` escalado por `devicePixelRatio` y redimensionado con `ResizeObserver`; una barra por sensor (`sensorCount`), altura = lectura / `adcMax`; marcador vertical de `line_position` en x = `line_position / ((n − 1) × 1000)`; con `line_lost` el marcador en `--warn` discontinuo y `line-lost` muestra `▲ LÍNEA PERDIDA` (texto, no solo color); `line-position` y `error` con `format.js` (FR-014, FR-015, research R7)
- [X] T026 [P] [US1] Escribir `src/velocista_sim/server/static/js/views/controller.js`: `pid-p`, `pid-i`, `pid-d`, `pid-out` con `formatPid` y `pwm-left`, `pwm-right` con `formatPwm` (−255…255 con signo visible) (FR-016)
- [X] T027 [P] [US1] Escribir `src/velocista_sim/server/static/js/views/trail-view.js`: canvas `trail-canvas` (DPR y `ResizeObserver`), escala uniforme en x e y ajustada a `bounds` con margen, eje y hacia arriba, polilínea de 1,5 px en `--accent` sin brillo, pose actual como triángulo blanco orientado por `theta`; atributo `data-points` = `trail.length`; franja `speed`, `distance`, `pose-x`, `pose-y`, `theta` con `format.js`; `btn-trail-clear` llama `clearTrail` (acción local, no envía nada); sin `isSim`, la tarjeta se oculta y la columna central muestra el aviso "Sin sim_truth: el robot real no informa su posición" (FR-018, research R7)
- [X] T028 [P] [US1] Escribir `src/velocista_sim/server/static/js/views/laps.js`: vuelta actual (`telemetry.lap.n` y `current_ms`), `lap-last`, `lap-best` (en `--best`), `lap-avg` calculados de `run.laps` mientras corre y de `summary` al terminar; `lap-history` con las vueltas, la más reciente primero; la tarjeta se oculta si `!hasLaps` (FR-020)
- [X] T029 [P] [US1] Escribir `src/velocista_sim/server/static/js/views/runs.js`: `summaries` como `li` con `data-run-id`, la más reciente primero: vueltas, mejor y promedio de vuelta (`formatSeconds`), salidas de pista, `track_id`, configuración inicial (`controller`, `kp`/`ki`/`kd`, `base_speed`) y `config_changed` como "sí"/"no"; `null` → `—` (FR-022)
- [X] T030 [US1] Completar `src/velocista_sim/server/static/js/views/topbar.js` con la franja de métricas: `run-status` (`SIN CORRIDA`/`● EN CORRIDA`, `data-state` `idle`/`running`), `run-id`, `lap-n` y `lap-target` (`n / objetivo` o solo `n`), `lap-current`, `battery` (oculto si `!hasBattery` o sin `battery_v`), `seq` y `seq-lost` (FR-008, FR-017, FR-019, FR-038)
- [X] T031 [US1] Escribir `src/velocista_sim/server/static/js/views/control.js` (botones y vueltas objetivo): `btn-start` habilitado solo con `open` y sin corrida (al pulsar limpia el rastro y envía `commands.start()`); `btn-stop` solo en corrida (`commands.stop()`); `btn-reset` solo sin corrida e `isSim` (envía `commands.reset()` y limpia el rastro) y oculto si `!isSim`; `lap-target-input` (oculto si `!hasLaps`) que en `change` llama `setLapTarget`, marca `aria-invalid="true"` si es inválido y, si `shouldAutoStop`, envía `stop` y `markAutoStop`; pestañas `tab-*` con `aria-selected` (control segmentado) (FR-007, FR-045)
- [X] T032 [US1] Integrar US1 en `src/velocista_sim/server/static/js/main.js`: registrar las vistas `sensors`, `controller`, `trail-view`, `laps`, `runs`, `control` y `topbar` en el bucle rAF; tras aplicar cada `telemetry` o `event lap`, si `shouldAutoStop(state)` enviar `commands.stop()` y `markAutoStop` (una sola vez por `run_id`); ocultar vistas y controles según `derived(state)` en cada `hello` (FR-006, FR-035) (depende de T023–T031)

**Checkpoint**: US1 completa; `uv run pytest tests/browser/test_panel_smoke.py tests/browser/test_panel_robot.py` pasa y los pasos 1–4, 8 y 17 de quickstart.md funcionan a mano.

---

## Phase 4: User Story 2 - Ajustar el controlador en vivo (Priority: P1)

**Goal**: sliders y campos de `kp`, `ki`, `kd`, `base_speed` y frecuencia que envían `set_config`
/ `set_rate` limitados durante el arrastre y reflejan siempre el último `config` confirmado.

**Independent Test**: con una sesión abierta, mover cada control y comprobar que se envía
`set_config`/`set_rate`, que el panel muestra el `config` de respuesta, que un valor rechazado
vuelve al confirmado y que el resumen indica `config_changed` (quickstart pasos 5–7).

### Tests for User Story 2 ⚠️

- [X] T033 [US2] Agregar a `tests/browser/test_panel_smoke.py` un test de ajuste contra el servidor real: llenar `kp-input` con `0.05` y confirmar → se envía `{"cmd":"set_config","params":{"kp":0.05}}` y `kp-input` muestra `0.0500` tras el `config`; arrastrar `kp-range` disparando 50 eventos `input` con valores crecientes durante 1 s y soltar → **≤ 7** `set_config` enviados en ese segundo y el **último** `set_config` enviado lleva exactamente el valor final del slider; `kp-input = -1` → `aria-invalid="true"` y nada enviado; `rate-input = 150` → inválido y nada enviado; `rate-input = 100` → `set_rate` con `hz: 100` y `rate-hz` muestra `100 Hz`; además, iniciar una corrida, cambiar `kp`, pulsar `btn-stop` y comprobar que el resumen más reciente en `summaries` muestra `config_changed` = "sí" (prueba independiente de US2); todos los frames válidos con `assert_frames_valid`; y extender `test_server_closing_shows_disconnected` (T021) para comprobar que `kp-input` y `rate-input` quedan deshabilitados con la conexión cerrada, que en la Fase 3 aún no existían (depende de T019)

### Implementation for User Story 2

- [X] T034 [P] [US2] Escribir `src/velocista_sim/server/static/js/throttle.js`: `throttle(fn, intervalMs = 200)` con envío inicial inmediato y envío final garantizado (`trailing`) del último valor; método `flush()` para forzar el envío pendiente al soltar (research R8)
- [X] T035 [US2] Extender `src/velocista_sim/server/static/js/state.js` con `drafts` (`kp`, `ki`, `kd`, `base_speed`, `rate_hz`, cada uno con `value` y `dragging`): al aplicar `config`, los controles que no se están arrastrando toman los valores confirmados; al resolverse como **rechazado** un pendiente `set_config` o `set_rate`, todos los drafts vuelven al último `config` (FR-013, data-model.md ControlDrafts)
- [X] T036 [US2] Implementar la pestaña de ajuste en `src/velocista_sim/server/static/js/views/control.js` (panel de `tab-tuning`): `kp-range`/`kp-input`, `ki-range`/`ki-input`, `kd-range`/`kd-input`, `base-speed-range`/`base-speed-input`, `rate-input`, con los rangos de research R9 (`kp` 0–0.2 paso 0.0005, `ki` 0–0.01 paso 0.0001, `kd` 0–5 paso 0.01, 4 decimales; `base_speed` 0–255 paso 1; `rate_hz` 10–100 paso 1); el slider en `input` envía `commands.setConfig({campo})` vía `throttle` de 200 ms por campo y `flush` en `change`/`pointerup`; el campo numérico envía en `change` sin throttle y acepta cualquier valor ≥ 0 para `kp`/`ki`/`kd` (fuera del recorrido, el slider queda en el extremo); `base_speed` entero 0–255; `rate_hz` entero 10–100 con `commands.setRate`; valores inválidos → `aria-invalid="true"` y no se envía (FR-009–FR-012)
- [X] T037 [US2] Integrar en `src/velocista_sim/server/static/js/main.js`: marcar/desmarcar `drafts.<campo>.dragging` en `pointerdown`/`pointerup` del slider, pasar los envíos por `sendCommand` (encolan pendientes) y re-renderizar los controles al llegar `config` o un `error` de `set_config`/`set_rate` (FR-013, US2-6)

**Checkpoint**: US1 y US2 funcionan juntas; los cambios se confirman en < 1 s (SC-002).

---

## Phase 5: User Story 3 - Elegir robot y pista, cargar pistas desde archivo (Priority: P2)

**Goal**: pestaña Robot y pista con catálogo (`list`), `load` de robot, cambio de pista por
reconexión con `track`/`robot` y `load_track` desde un archivo JSON local.

**Independent Test**: sin corrida, pedir el catálogo, cargar un robot con `load` y ver el nuevo
`hello`; cargar un archivo de pista válido (nuevo `track_id`, rastro limpio) y uno inválido
(error local o `invalid_track`) (quickstart pasos 9–13, 16).

### Tests for User Story 3 ⚠️

- [ ] T038 [US3] Agregar a `tests/browser/test_panel_smoke.py` un test de robot y pista contra el servidor real: tras abrir se envía `list` y `robot-select`/`track-select` listan el catálogo con el vigente marcado; elegir `velocista-01` en `robot-select` → envía `load`, llega `hello`+`config` y `trail-canvas` queda con `data-points="0"`; `track-file` con `config/tracks/oval-01.json` → envía `load_track` y `track-id` muestra su id; `track-file` con un `.txt` no JSON → `li[data-kind=local]` en `log` y ningún frame enviado; `track-file` con un JSON que no cumple track v1 (el objeto `message` de `contract/examples/invalid/track/gaps-overlap.json` guardado en un archivo temporal) → `li[data-kind=error]` con `invalid_track` y `track-id` sin cambios (US3-6, SC-005); elegir otra entrada en `track-select` y aceptar el diálogo (`page.on("dialog", lambda d: d.accept())`) → se abre un WebSocket nuevo cuya URL tiene `track=<id>` y `robot=velocista-01`, llega un `hello` con otro `session_id` y `track-id` muestra la pista elegida (US3-3, FR-026); cancelar el diálogo → no se reconecta; con un servidor falso (`route_web_socket`) que envía `hello`, `config` y un `error` `unknown_track` sin `cmd` (como hace el simulador ante una pista inexistente) → `li[data-kind=error]` con `unknown_track` y `conn-status` sigue `open` (FR-026, SC-005); con una corrida activa `robot-select`, `track-select`, `track-file` están deshabilitados con el texto "Detené la corrida para cambiar esto"; frames válidos con `assert_frames_valid` (depende de T019)

### Implementation for User Story 3

- [ ] T039 [US3] Extender `src/velocista_sim/server/static/js/state.js`: al resolverse como **aceptado** un pendiente `load` limpiar el rastro y reiniciar la calibración, y uno `load_track` limpiar el rastro aunque el `track_id` no cambie (research R5, FR-018); un `error` `run_active`, `unknown_robot`, `unknown_track` o `invalid_track` se registra con su `code` y `message` y la pista vigente no cambia
- [ ] T040 [US3] Escribir `src/velocista_sim/server/static/js/views/robot-track.js` (panel de `tab-robot-track`, oculto si `!isSim`): `robot-select` y `track-select` con `catalog.robots`/`catalog.tracks`, marcando `hello.robot.id` y `config.track_id`; `btn-catalog-refresh` envía `commands.list()`; elegir robot envía `commands.load(id)`; elegir pista pide confirmación con `confirm("Se abrirá una sesión nueva: se pierden el historial y la calibración de esta sesión. ¿Continuar?")` y, si se acepta, reconecta con `buildUrl({track: id, robot: hello.robot.id})` tras `resetSession`; `track-file` lee el archivo con `File.text()`, si `JSON.parse` falla registra el error local "El archivo no es JSON válido" y no envía nada, si no envía `commands.loadTrack(objeto)`; todo deshabilitado con corrida activa o conexión cerrada, con el texto "Detené la corrida para cambiar esto" (FR-024–FR-028)
- [ ] T041 [US3] Integrar en `src/velocista_sim/server/static/js/main.js`: registrar la vista `robot-track`, exponer una función `reconnect({track, robot})` reutilizada por `btn-reconnect` y por el cambio de pista, y mostrar `unknown_track`/`unknown_robot` de la conexión en el registro (FR-026)

**Checkpoint**: US1, US2 y US3 funcionan de forma independiente.

---

## Phase 6: User Story 4 - Calibrar el perfil con valores medidos (Priority: P2)

**Goal**: pestaña Calibración con los 12 parámetros de `set_profile`, aplicar en un único
comando, borrar con `null` y marcar "medido"/"por defecto" según las respuestas aceptadas.

**Independent Test**: sin corrida, fijar `wheelbase_m = 0.128` → `MEDIDO 0.128 m`; `adc_noise = -5`
→ error visible y ninguna marca cambia; borrar → `POR DEFECTO` (quickstart pasos 14–16).

### Tests for User Story 4 ⚠️

- [ ] T042 [US4] Agregar a `tests/browser/test_panel_smoke.py` un test de calibración contra el servidor real: `calib-wheelbase_m = 0.128` + `btn-calib-apply` → envía un único `set_profile` con `measured.wheelbase_m = 0.128` y `calib-wheelbase_m-state` dice `MEDIDO`; `calib-adc_noise = -5` + aplicar → `li[data-kind=error]` en `log` con `out_of_range` o `invalid_params` y ninguna marca cambia; `calib-adc_white = abc` → `aria-invalid="true"` y nada enviado; `btn-calib-clear-wheelbase_m` → envía `measured.wheelbase_m = null` y el estado vuelve a `POR DEFECTO`; frames válidos con `assert_frames_valid` (depende de T019)

### Implementation for User Story 4

- [ ] T043 [P] [US4] Escribir `src/velocista_sim/server/static/js/profile-params.js`: arreglo congelado con los 12 parámetros de la tabla de data-model.md (`key`, `label`, `unit`, `range` como texto, `integer`), en este orden y con estos valores exactos: `sensor_pitch_m` "Separación entre sensores" m "> 0" no; `sensor_offset_m` "Distancia de la regleta al eje" m "> 0" no; `adc_white` "Lectura sobre blanco" ADC "0–65535" sí; `adc_black` "Lectura sobre negro" ADC "0–65535" sí; `adc_noise` "Ruido de la regleta" "ADC (±)" "≥ 0" sí; `max_speed_mps` "Velocidad máxima (PWM 255)" m/s "> 0" no; `motor_tau_ms` "Constante de tiempo del motor" ms "> 0" no; `wheelbase_m` "Distancia entre ruedas" m "> 0" no; `max_lateral_accel_mps2` "Agarre lateral máximo" m/s² "> 0" no; `turbine_suction_n` "Succión de la turbina" N "≥ 0" no; `encoder_ticks_per_rev` "Pulsos del encoder por vuelta" ticks "≥ 1" sí; `control_period_ms` "Período de control" ms "> 0" no; más `parseDraft(param, text)` que solo verifica número finito (y entero si `integer`); el rango lo decide el servidor (FR-029, FR-030)
- [ ] T044 [US4] Extender `src/velocista_sim/server/static/js/state.js` con `calibration`: un registro por parámetro (`measured: number | null`, `draft: string`); al resolverse como **aceptado** un pendiente `set_profile`, fijar `measured` con lo enviado (o `null` al borrar) solo en los parámetros enviados; rechazado → ninguna marca cambia (todo o nada); `hello` nuevo o sesión nueva → todos `measured = null` (FR-032) (depende de T043)
- [ ] T045 [US4] Escribir `src/velocista_sim/server/static/js/views/calibration.js` (panel de `tab-calibration`, oculto si `!isSim`, con desplazamiento interno): por parámetro, rótulo en español, unidad, rango como ayuda, campo `calib-<key>`, estado `calib-<key>-state` (`MEDIDO <valor> <unidad>` o `POR DEFECTO`) y botón `btn-calib-clear-<key>` (envía `commands.setProfile({[key]: null})`, habilitado solo si hay `measured`); `btn-calib-apply` valida con `parseDraft` todos los campos con texto, marca los inválidos con `aria-invalid="true"` y no envía nada si hay alguno; si todos son válidos envía **un único** `commands.setProfile(measured)`; todo deshabilitado con corrida activa o conexión cerrada, con "Detené la corrida para cambiar esto" (FR-029–FR-033)
- [ ] T046 [US4] Integrar en `src/velocista_sim/server/static/js/main.js`: registrar la vista `calibration` en el bucle rAF y re-renderizarla al resolverse un pendiente `set_profile` o al llegar un `hello` (depende de T044, T045)

**Checkpoint**: las cuatro historias funcionan de forma independiente.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: distribución, accesibilidad, documentación y validación final.

- [ ] T047 [P] Agregar a `tests/browser/test_panel_smoke.py` un test de distribución: con viewport 1440 × 900, `document.documentElement.scrollHeight <= innerHeight` y `scrollWidth <= innerWidth` (FR-044); con 1000 × 900, sin desplazamiento horizontal y la tarjeta Control antes que la Regleta en el orden visual; la página no contiene `<img>`, `<video>` ni reglas con `animation`/`transition` (FR-043, SC-010)
- [ ] T048 [P] Crear `tests/browser/test_panel_load.py` con un test marcado `@pytest.mark.slow` (además de `browser` por el `conftest.py`), que queda **excluido de `uv run pytest` y de la CI** por `addopts = "-m 'not slow'"` y se corre con `uv run pytest -m slow tests/browser/test_panel_load.py`: abre el panel contra `live_url`, fija `rate-input = 100`, pulsa `btn-start` (vueltas objetivo vacío) y durante **30 s** de corrida comprueba cada pocos segundos que `seq` avanza; al final verifica `seq-lost` = 0, que `trail-canvas` tiene `data-points` > 0, que un cambio de `kp-input` se confirma (aparece en `kp-input` tras el `config`) en < 1 s y que `btn-stop` termina la corrida y agrega un resumen; sin errores de consola (SC-003, versión corta; la de 5 min es manual, quickstart paso 20)
- [ ] T049 [P] Revisar `src/velocista_sim/server/static/panel.css` y las vistas: todo valor numérico usa `--font-mono` con `tabular-nums` y `min-width` en `ch` (SC-009); los estados (`line_lost`, `off_track`, `error`, conexión) llevan texto o símbolo además del color (SC-011); el texto chico nunca usa `--accent` (solo `--accent-text`)
- [ ] T050 [P] Agregar la sección "Panel de laboratorio" a `README.md`: abrir `http://localhost:8000/` con `uv run velocista-sim`, qué muestra cada columna, cómo instalar Chromium para los tests (`uv run playwright install chromium`), `uv run pytest -m browser`, la prueba de carga `uv run pytest -m slow tests/browser/test_panel_load.py` (no corre en CI) y la verificación manual de 5 min a 100 Hz antes de cada PR (quickstart paso 20), y que el panel es el ejemplo de cliente v1 para el front (`connection.js`, `commands.js`, `state.js`, SC-007)
- [ ] T051 Revisar que cada módulo JS de `src/velocista_sim/server/static/js/` tenga un comentario de cabecera en español con su responsabilidad y que `state.js` documente, junto a cada `case` de `applyMessage`, qué efecto tiene el mensaje (SC-007)
- [ ] T052 Ejecutar `uv run pytest` completo (incluye `tests/browser/` con Chromium instalado) y corregir fallos; confirmar que los tests existentes de `/health` y `/ws` pasan sin modificaciones en sus asserts
- [ ] T053 Recorrer a mano la tabla de la sección 2 de `specs/003-panel-laboratorio/quickstart.md` (pasos 1–20, incluida la corrida de 5 min a 100 Hz antes de abrir el PR) con `uv run velocista-sim` en una ventana de 1440 × 900, y correr `uv run pytest -m slow tests/browser/test_panel_load.py` y anotar cualquier desvío como tarea nueva en este archivo

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias.
- **Foundational (Phase 2)**: depende de Setup; **bloquea** todas las historias.
- **US1 (Phase 3)**: depende de Foundational. Es el MVP.
- **US2 (Phase 4)**: depende de Foundational; comparte `control.js`, `state.js` y `main.js` con US1,
  por lo que en la práctica se hace después de US1 (sus tests agregan casos a
  `tests/browser/test_panel_smoke.py`, creado en T019).
- **US3 (Phase 5)** y **US4 (Phase 6)**: dependen de Foundational y de que exista
  `tests/browser/test_panel_smoke.py` (T019); son independientes entre sí salvo por ediciones
  secuenciales de `state.js` y `main.js`.
- **Polish (Phase 7)**: después de las historias que se quieran entregar.

### User Story Dependencies

- **US1 (P1)**: solo Foundational.
- **US2 (P1)**: Foundational; usa los botones de `control.js` de US1 solo como contenedor (la
  pestaña `tab-tuning` es independiente).
- **US3 (P2)**: Foundational; integra con la limpieza del rastro de US1 (`trail.js`, T022).
- **US4 (P2)**: Foundational; ninguna dependencia funcional con US2/US3.

### Within Each User Story

- Tests primero (deben fallar), luego módulos puros (`trail.js`, `throttle.js`,
  `profile-params.js`), luego `state.js`, luego vistas y por último la integración en `main.js`.
- Archivos compartidos (`state.js`, `main.js`, `control.js`, `topbar.js`,
  `tests/browser/test_panel_smoke.py`) se editan en secuencia, nunca en paralelo.

### Parallel Opportunities

- Setup: T003 y T004 en paralelo (T002 primero si se toca `pyproject.toml` a la vez: hacer T002 y
  luego T003).
- Foundational: T006, T010, T011, T012, T013 en paralelo; T015 y T016 en paralelo tras T014.
- US1: T019 y T020 (tests en archivos distintos; T021 va después de T019 porque comparte
  archivo) y T022, T025, T026, T027, T028, T029 (vistas en archivos propios).
- US2: T034 en paralelo con T033.
- US4: T043 en paralelo con T042.
- Polish: T047, T048, T049 y T050 en paralelo.

---

## Parallel Example: User Story 1

```bash
# Tests de US1 (archivos distintos):
Task: "Crear tests/browser/test_panel_smoke.py (humo: start → EN CORRIDA, seq avanza, resumen)"
Task: "Crear tests/browser/test_panel_robot.py (robot real simulado con route_web_socket)"

# Módulos y vistas de US1 (un archivo cada uno):
Task: "trail.js: buffer circular de 5000 puntos"
Task: "views/sensors.js: canvas de la regleta"
Task: "views/controller.js: PID y PWM"
Task: "views/trail-view.js: canvas del rastro y franja de valores"
Task: "views/laps.js: vueltas"
Task: "views/runs.js: resúmenes de corridas"
```

## Parallel Example: Foundational

```bash
Task: "tests/support/live_server.py: extraer uvicorn en hilo"
Task: "panel.css: tokens de R11 y grilla de tres columnas"
Task: "js/format.js: formato fijo por magnitud"
Task: "js/commands.js: 9 constructores puros"
Task: "js/connection.js: URL ws/wss, connect, send"
```

---

## Implementation Strategy

### MVP First (solo User Story 1)

1. Phase 1: Setup.
2. Phase 2: Foundational (crítica: entrega en `/`, conexión, estado base, comandos validados).
3. Phase 3: US1.
4. **PARAR y VALIDAR**: `uv run pytest` + quickstart pasos 1–4, 8 y 17.
5. Desplegar en Railway y comprobar `wss` (quickstart sección 3).

### Incremental Delivery

1. Setup + Foundational → la página conecta y muestra `hello`/`config`.
2. + US1 → laboratorio de observación y control de corridas (MVP).
3. + US2 → ajuste del PID en vivo (completa el P1).
4. + US3 → robots, pistas del catálogo y pistas desde archivo.
5. + US4 → calibración del perfil.
6. Polish → distribución verificada, README, validación de quickstart.

---

## Notes

- [P] = archivos distintos y sin dependencias pendientes.
- [USn] mapea cada tarea a su historia para trazabilidad.
- No se modifica `contract/`, `world/`, `robot/` ni la lógica de sesión del servidor; si alguna
  tarea pareciera requerirlo, detenerse: el panel solo usa el contrato v1 (FR-003, principio I).
- Commit después de cada tarea o grupo lógico, con Conventional Commits en español.
