---

description: "Lista de tareas para implementar el simulador de velocista por WebSocket"
---

# Tasks: Simulador de velocista accesible por WebSocket (contrato v1)

**Input**: documentos de diseño en `specs/002-simulador/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: SÍ se incluyen. La spec los exige (FR-005, SC-002, SC-003, SC-007) y la constitución
(principio VII) pide validar todo mensaje emitido contra el contrato. Dentro de cada historia, los
tests se escriben primero y deben FALLAR antes de implementar.

**Organization**: tareas agrupadas por historia de usuario (US1 = P1, US2 = P2, US3 = P3), cada
una implementable y verificable por separado.

## Formato: `[ID] [P?] [Story] Descripción`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece la tarea (US1, US2, US3)
- Cada descripción indica la ruta exacta del archivo

## Convenciones de ruta

Proyecto único: código en `src/velocista_sim/` (paquetes `world`, `robot`, `server` junto al
`contract` existente), catálogo en `config/`, tests en `tests/`. Identificadores en inglés;
docstrings, comentarios y `error.message` en español (constitución, flujo de desarrollo).

---

## Phase 1: Setup (infraestructura compartida)

**Purpose**: dependencias, configuración de pytest y esqueleto de paquetes.

- [ ] T001 Agregar dependencias con uv: `uv add numpy` (lecturas vectorizadas, research R3) y `uv add --dev httpx websockets` (TestClient y cliente de extremo a extremo, research R10/R14); verificar que `pyproject.toml` y `uv.lock` quedan actualizados
- [ ] T002 Configurar pytest en `pyproject.toml`: registrar el marcador `slow` ("prueba de tiempo real, lenta") y cambiar `addopts` a `"-ra -m 'not slow'"`; `.github/workflows/tests.yml` no cambia: la prueba `slow` no se corre en CI, solo a mano con `uv run pytest -m slow`
- [ ] T003 [P] Crear los paquetes vacíos con docstring en español: `src/velocista_sim/world/__init__.py`, `src/velocista_sim/robot/__init__.py`, `src/velocista_sim/server/__init__.py`
- [ ] T004 [P] Crear las carpetas de tests con `__init__.py` vacío donde haga falta para importar el helper: `tests/support/__init__.py`, `tests/integration/`, `tests/slow/`

---

## Phase 2: Foundational (prerrequisitos bloqueantes)

**Purpose**: reglas de arquitectura, helper de validación de mensajes, catálogo, settings y
parseo de comandos; todo lo usan las tres historias.

**⚠️ CRITICAL**: ninguna historia puede empezar hasta terminar esta fase.

- [ ] T005 [P] Escribir `tests/unit/test_architecture.py`: recorrer con `ast` todos los `.py` de `src/velocista_sim/world/` y `src/velocista_sim/robot/` y fallar si `robot` importa `velocista_sim.world` o `velocista_sim.server`, si `world` importa `velocista_sim.robot` o `velocista_sim.server`, o si cualquiera importa `time`, `datetime`, `random` o `asyncio` (research R2; principios III y VI)
- [ ] T006 [P] Crear `tests/support/contract_client.py` con: (a) `MessageChecker`, que recibe mensajes uno a uno, guarda el último `hello` y falla (`AssertionError` con la violación) si `validate_message(msg, ultimo_hello)` no es `ok`, si el primer mensaje no es `hello` y el segundo no es `config`, si `t_ms` decrece, si `telemetry.seq` no empieza en 0 o no crece de a 1 (permitir saltos solo con un flag `allow_drops`), si hay más de un `run_finished` por `run_id`, si un `off_track` no va seguido de `run_finished`, o si algún mensaje contiene la clave `centerline` a cualquier profundidad (FR-008); expone por instancia los `type`, `event` y `code` vistos (sin registro global; lo usa T053); (b) `ContractClient`, envoltorio de la conexión WebSocket de `fastapi.testclient.TestClient` cuyo `receive_json()` pasa cada mensaje por un `MessageChecker`, con helpers `send_cmd(**campos)` y `wait_for(predicate, max_msgs)` (research R10)
- [ ] T007 [P] Crear el script versionado `tools/gen_oval.py` (solo biblioteca estándar; parámetros por línea de comandos con los valores de abajo como defecto; escribe el JSON con `indent=2` y termina con error en español si `validate_track` falla) y generar con él `config/tracks/oval-01.json` (pista track v1): estadio cerrado centrado en (1,50; 1,25), tablero `3,00 × 2,50` m, rectas de 1,50 m, radio 0,60 m, puntos cada ≈ 5 mm (L ≈ 6,770 m, ≈ 1354 puntos), `line_width` 0,019, `gaps: []`, `start.at` 0,10 sobre la recta inferior en sentido antihorario, `rules_profile "lgr2026"`, `id "oval-01"` (research R12); comprobar que `validate_track` da `ok` y que volver a correr `uv run python tools/gen_oval.py` reproduce el archivo byte a byte
- [ ] T008 [P] Crear `config/robots/velocista-01.json` como copia exacta del campo `message` de `contract/examples/valid/robot-profile/velocista-01-default.json` (contracts/config-files.md)
- [ ] T009 [P] Implementar `src/velocista_sim/server/settings.py`: dataclass `Settings` con `port` (`PORT`, defecto 8000), `seed` (`VELOCISTA_SEED`, defecto 1), `config_dir` (`VELOCISTA_CONFIG_DIR`, defecto la carpeta `config/` del repo localizada subiendo desde el módulo, como `contract/schemas.py`), `max_sessions` (`VELOCISTA_MAX_SESSIONS`, entero ≥ 1, defecto 20), `default_robot = "velocista-01"`, `default_track = "oval-01"`; `Settings.from_env(environ)` con error en español si un valor no es entero válido (data-model.md, Settings)
- [ ] T010 Implementar `src/velocista_sim/server/catalog.py`: `Catalog` inmutable con `profiles: dict[str, dict]` y `tracks: dict[str, dict]`; `load_catalog(config_dir, settings)` lee `robots/*.json` y `tracks/*.json`, valida con `validate_profile`/`validate_track` y falla el arranque (excepción con mensaje en español: archivo, regla y path) si el nombre de archivo ≠ `id`, si faltan `default_robot` o `default_track`, o si un perfil no tiene `motors = 2` y `encoders`, `imu`, `turbine` efectivos en `false` (research R12; depende de T007, T008, T009)
- [ ] T011 [P] Escribir `tests/unit/test_catalog.py`: el catálogo real carga con `velocista-01` y `oval-01`; `config/robots/velocista-01.json` es idéntico al `message` del ejemplo del contrato; casos de fallo en `tmp_path` (nombre ≠ `id`, perfil con `encoders: true`, pista inválida, falta el default) levantan error
- [ ] T012 [P] Escribir `tests/unit/test_commands.py` cubriendo la precedencia de errores de contracts/ws-session.md: no-JSON, `NaN`/`Infinity` y no-objeto → `invalid_json` sin `cmd`; `v` ≠ 1 → `unsupported_version` (con `cmd` si es string); `cmd` ausente/no string/desconocido → `unknown_cmd`; `set_config` vacío o con tipo incorrecto → `invalid_params`; `set_rate` `hz = 150` y `base_speed = 300` → `out_of_range`; `set_profile` con un parámetro de `hello` → `invalid_params`; `wheelbase_m` negativo → `out_of_range`; `load_track` con pista inválida bajo `/track/…` → `invalid_track`; violaciones mixtas → gana `invalid_params`; todos los `message` en español; se pueden reutilizar los ejemplos de `contract/examples/invalid/commands/`
- [ ] T013 Implementar `src/velocista_sim/server/commands.py`: `parse(frame: str) -> Command | CommandError` según research R8 (`json.loads` con `parse_constant` que rechaza `NaN`/`Infinity`; `v`; `cmd`; `validate_command` y mapeo de la primera violación por grupos: `/track/…` de `load_track` → `invalid_track`; `required`, `type`, `enum`, `const`, `minProperties`, `propertyNames`, `not`, `anyOf`, `oneOf` → `invalid_params`; `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum` → `out_of_range`; con ambos grupos gana `invalid_params`); `CommandError` lleva `code`, `cmd` (siempre que `cmd` sea string) y `message` en español; helper `error_message(err, t_ms)` que arma el mensaje `error` del contrato (hace pasar T012)

**Checkpoint**: arquitectura vigilada, catálogo y comandos listos; las historias pueden empezar.

---

## Phase 3: User Story 1 - El optimizador corre una configuración y recibe el resumen (Priority: P1) 🎯 MVP

**Goal**: sesión por conexión con `hello` + `config`, mundo (óvalo, física, regleta con ruido),
robot con PID a bordo, telemetría a `rate_hz`, eventos de corrida y comandos `start`, `stop`,
`set_config`, `set_rate`, `list`, `reset`.

**Independent Test**: con `TestClient` (reloj acelerado) o un uvicorn local, `set_config` →
`start` → esperar 3 `event lap` → `stop` → `run_finished` con `summary` correcto; todo mensaje
recibido valida contra el contrato (quickstart §1 y §2).

### Tests de User Story 1 ⚠️

> Escribirlos primero y comprobar que FALLAN.

- [ ] T014 [P] [US1] Escribir `tests/unit/test_world_track.py`: `TrackGeometry.from_track` sobre `oval-01` da `length` ≈ 6,770 m (tolerancia 1 mm) y `closed = True`; `pose_at(start_s)` cae sobre la recta inferior con heading ≈ 0 (sentido antihorario); `project` de un punto de la línea devuelve su `s`; con `oval-small` (ejemplo `contract/examples/valid/commands/load_track/oval-small.json`) los tramos con tinta excluyen el corte; `ink_candidates` de una caja lejos de la línea devuelve vacío
- [ ] T015 [P] [US1] Escribir `tests/unit/test_world_sensors.py`: con el robot centrado sobre la recta, los sensores centrales leen ≈ `adc_black` y los extremos ≈ `adc_white`; lecturas intermedias para cobertura parcial con `cov = clip((line_width/2 + a/2 − d) / a, 0, 1)`; todas en `0 … 2^adc_bits − 1` y longitud `line_sensors`; sobre un corte todas ≈ `adc_white`; con `adc_noise = 0` la lectura es determinista y con el mismo `rng` sembrado dos lecturas coinciden
- [ ] T016 [P] [US1] Escribir `tests/unit/test_world_physics.py`: PWM constante → velocidad de rueda converge a `pwm/255 · max_speed_mps` con constante `motor_tau_ms` (`v += (v_cmd − v)·(1 − exp(−dt/τ))`); PWM iguales → recta; diferencia de PWM → giro con `ω = (v_r − v_l)/wheelbase_m`; si `|v·ω| > max_lateral_accel_mps2` se recorta `ω = sign(ω)·a_max/|v|` (FR-011); `theta` normalizado a (−π, π]; `distance_m` ≥ 0 y creciente; `battery_v = round(nominal_v − 0,25·(|left|+|right|)/510, 3)` (research R13)
- [ ] T017 [P] [US1] Escribir `tests/unit/test_world_detection.py`: con la pose forzada a avanzar por la línea central, `detect` emite `LapCompleted(lap=1, lap_ms=…)` al completar `L` de progreso; retroceder sobre la salida no cuenta vuelta; sin tinta durante más de 0,10 m recorridos por el centro de la regleta o más de 1,0 s → `OffTrack("line_lost")`; eje fuera del tablero `[0, width] × [0, height]` → `OffTrack` inmediato; cruzar un corte de 0,02 m no produce `OffTrack` (research R9)
- [ ] T018 [P] [US1] Escribir `tests/unit/test_robot_line.py`: normalización `n_i = clip((s_i − adc_white)/(adc_black − adc_white), 0, 1)` con piso 0,1; `line_lost` si `Σ n_i < 0,3`; `line_position = round(1000·Σ i·n_i/Σ n_i)` en `0 … 15000`; `error = line_position − 7500`; con la línea perdida, `0` si la última posición fue menor que el centro y `15000` si no; `adc_black == adc_white` → todo `n_i = 0` (research R7, FR-018)
- [ ] T019 [P] [US1] Escribir `tests/unit/test_robot_pid.py`: `p = kp·e`, `I += e`, `i = ki·I`, `d = kd·(e − e_prev)` con `d = 0` en el primer tick tras `reset`; `left = clip(round(base_speed + out), −255, 255)`, `right = clip(round(base_speed − out), −255, 255)`; con `running = False` la salida tiene `p = i = d = out = 0` y motores 0 pero sí `line_position`; `p`, `i`, `d`, `out` acotados a ±1e9 con ganancias extremas; con `control_period_ms` 2 corre en cada paso (FR-017, FR-019, FR-020)
- [ ] T020 [P] [US1] Escribir `tests/integration/test_session_core.py` (núcleo `Session` sin E/S, cada mensaje pasa por `MessageChecker`): `open()` da `hello` (`source "sim"`, `velocista-01`) y `config` (`kp 0.045`, `ki 0`, `kd 0.9`, `base_speed 180`, `rate_hz 50`, `track_id "oval-01"`) con `t_ms = 0`; telemetría cada 10 pasos con `running = false`, sin `run_id` ni `lap`, con `battery_v` y `sim_truth`; SC-001 (config por defecto: ≥ 3 vueltas sin `off_track`, `lap_ms` ≈ 3,4 s, luego `stop` → un `run_finished` con `laps ≥ 3`); SC-005 (`kp = 0` → `off_track` `line_lost` + `run_finished` con `off_tracks = 1` y `laps = 0`, `best_lap_ms = null`, en < 10 s simulados); `set_config` parcial durante la corrida → `config` nuevo y `summary.config_changed = true` con la config inicial en `summary.config`; `set_rate` 20 → telemetría cada 25 pasos; `set_rate` a mitad de una corrida no altera la simulación (misma corrida en dos sesiones gemelas, una con `set_rate 20` en el paso 1000 y otra sin él → mismo `summary` y mismo `sim_truth` en los `t_ms` que ambas informan); `list` → `catalog`; `reset` sin corrida vuelve a la salida (visible en `sim_truth`); `start` con corrida → `run_active`; `stop` sin corrida → `no_run` y sin `run_finished`; `base_speed 0` no termina sola; SC-003 (dos sesiones con la misma semilla y los mismos comandos en los mismos pasos → `summary` y telemetría idénticos; dos corridas seguidas con la misma config → lecturas de sensores distintas); SC-007 (cada rechazo deja igual `config` y la telemetría siguiente que en una sesión gemela sin el comando rechazado)
- [ ] T021 [P] [US1] Escribir `tests/integration/test_ws_session.py` con `TestClient(create_app(settings, clock=reloj_acelerado_x20))` y `ContractClient`: escenarios de aceptación US1-1 a US1-11 por WebSocket (apertura `hello` → `config`; `seq` desde 0 de a 1; `set_config` → `config`; `start` → `run_started` y telemetría con `run_id` y `lap`; `event lap` con `lap.n` creciente; `stop` → exactamente un `run_finished`; `kp 0` → `off_track` + `run_finished`; `set_rate`; `list`; `reset`); frames inválidos (`invalid_json`, `unknown_cmd`, `unsupported_version`) no cortan la sesión; US1-12: dos conexiones simultáneas, una corre y la otra mantiene `running = false` y su `config` sin cambios
- [ ] T022 [P] [US1] Escribir `tests/unit/test_pacer.py`: con un reloj falso, `Pacer` ejecuta `floor((reloj − t_base)/0,002)` pasos, como máximo 50 por tanda, y mueve `t_base` si el atraso supera 100 ms; la cola de salida descarta `telemetry` cuando ya hay 25 pendientes (el `seq` se consume igual) y nunca descarta `hello`, `config`, `event`, `error` ni `catalog`; con más de 1.000 no-telemetría pendientes pide cerrar con código 1008 (research R11)

### Implementación de User Story 1

- [ ] T023 [P] [US1] Implementar `src/velocista_sim/world/params.py`: `WorldParams` (dataclass `frozen`) con `line_sensors`, `sensor_pitch_m`, `sensor_offset_m`, `adc_bits`, `adc_white`, `adc_black`, `adc_noise`, `max_speed_mps`, `motor_tau_ms`, `wheelbase_m`, `max_lateral_accel_mps2`, `battery_nominal_v` y `WorldParams.from_effective(effective: dict)` (contracts/world-robot.md)
- [ ] T024 [P] [US1] Implementar `src/velocista_sim/robot/params.py`: `RobotParams` (`line_sensors`, `adc_white`, `adc_black`, `control_period_ms`), `PidConfig` (`kp`, `ki`, `kd`, `base_speed`) y `ControlOutput` (`line_position`, `line_lost`, `error`, `p`, `i`, `d`, `out`, `left`, `right`), todas `frozen`, sin importar `world` ni `server`
- [ ] T025 [US1] Implementar `src/velocista_sim/world/track.py`: `TrackGeometry.from_track(track)` con `points` (P, 2), `cum_s`, `length` (con tramo de cierre si `closed`), `closed`, `ink_a`/`ink_b` (M, 2) = centerline menos `gaps`, grilla de celdas de 0,05 m → índices de tramos con tinta, `board`, `line_width`, `start_s`; operaciones `pose_at(s)`, `project(x, y, hint)` (búsqueda en ventana de índices alrededor de `hint`) e `ink_candidates(bbox)` (research R3, R9; hace pasar T014)
- [ ] T026 [US1] Implementar `src/velocista_sim/world/sensors.py`: posiciones vectorizadas de los 16 sensores (índice 0 a la izquierda, centrados, a `sensor_offset_m` delante del eje, cada `sensor_pitch_m`), distancia punto–segmento 16 × K con numpy contra `ink_candidates`, cobertura `cov = clip((line_width/2 + a/2 − d)/a, 0, 1)` con `a = sensor_pitch_m`, lectura `round(adc_white + (adc_black − adc_white)·cov + ruido)` con ruido entero uniforme en `[−adc_noise, +adc_noise]` del `rng` recibido, recortada a `0 … 2^adc_bits − 1`; función aparte que devuelve si algún sensor tiene cobertura > 0 sin ruido (para detección) (FR-012; hace pasar T015; depende de T025)
- [ ] T027 [P] [US1] Implementar `src/velocista_sim/world/physics.py`: estado de ruedas y pose, paso de `dt = 0,002 s` según research R4 (velocidad pedida proporcional al PWM, motor de primer orden con discretización exacta, cinemática diferencial, recorte por agarre lateral, integración y `theta` normalizado a (−π, π]) y `battery_v` según R13 (hace pasar T016)
- [ ] T028 [US1] Implementar `src/velocista_sim/world/world.py`: clase `World` con `DT_S = 0.002`, `reset_to_start()` (eje sobre `start.at` orientado por la tangente, ruedas y PWM a 0, contadores a 0), `set_params`, `set_motor_pwm`, `read_sensors(rng)`, `step()`, `begin_run(t_ms)`, `detect(t_ms) -> list[LapCompleted | OffTrack]` (progreso desenvuelto en `(−L/2, L/2]`, vueltas solo en pistas `closed`, salida por 0,10 m de regleta sin tinta, 1,0 s sin tinta o eje fuera del tablero), `truth()` (`x`, `y`, `theta`, `speed_mps`, `distance_m`) y `battery_v()`; dataclasses `LapCompleted(lap, lap_ms)` y `OffTrack(reason="line_lost")`; exportar lo público en `src/velocista_sim/world/__init__.py` (FR-013, FR-014, FR-015; hace pasar T017; depende de T023, T025, T026, T027)
- [ ] T029 [P] [US1] Implementar `src/velocista_sim/robot/line.py`: `line_position(sensors, params, last_position) -> (position, lost)` y `line_error(position, line_sensors)` según research R7 (hace pasar T018)
- [ ] T030 [P] [US1] Implementar `src/velocista_sim/robot/pid.py`: PID discreto por tick de control (`integral`, `prev_error` `None` tras reinicio, términos acotados a ±1e9) según research R7
- [ ] T031 [US1] Implementar `src/velocista_sim/robot/robot.py`: clase `Robot(params, config)` con `reset()`, `set_config(PidConfig)`, `set_params(RobotParams)` y `tick(sensors, running) -> ControlOutput` (sin corrida: control y motores en 0); exportar lo público en `src/velocista_sim/robot/__init__.py` (FR-017 a FR-020; hace pasar T019; depende de T024, T029, T030)
- [ ] T032 [US1] Implementar `ControllerConfig` (dataclass `frozen`: `controller "pid"`, `kp`, `ki`, `kd` float ≥ 0 con defecto 0,045 · 0 · 0,9, `base_speed` int 0–255 con defecto 180; `merged(set_config_cmd)` que combina también los parámetros sueltos de `params`; `to_message()` con la forma `{controller, params:{kp,ki,kd}, base_speed}`) y `Run` (`run_id "r-<n>"`, `number`, `start_config`, `config_changed`, `track_id`, `lap_times_ms`, `lap_start_ms`, `off_tracks`; `summary()` con `laps`, `best_lap_ms`, `avg_lap_ms = round(mean)` o `null` sin vueltas, `off_tracks`, `track_id`, `config`, `config_changed`) en `src/velocista_sim/server/session.py` (data-model.md)
- [ ] T033 [US1] Implementar la clase `Session` en `src/velocista_sim/server/session.py`: `Session(catalog, settings, robot_id, track_id)` con `session_id = "s-" + 8 hex`, `open() -> list[dict]` (`hello` + `config` con `t_ms = 0`; registra en el log INFO el perfil efectivo con el origen de cada valor, principio V), `submit(frame)` (encola en `inbox`) y `step() -> list[dict]` con el orden de data-model.md (comandos del `inbox` → tick de control → `world.step()` → `detect` con corrida → telemetría si toca), `t_ms = step_index · 2`, calendario de control y de telemetría con aritmética entera (research R5), `rng = PCG64(SeedSequence([seed, 0]))` fuera de corrida y uno nuevo `[seed, n]` en cada `start` (R6), telemetría con `seq`, `running`, `run_id`/`lap` solo con corrida, `sensors`, `line_position`, `line_lost`, `error`, `control`, `motors`, `battery_v`, `sim_truth` y nunca `odometry` (FR-006, FR-007); el `hello` toma las capacidades del perfil efectivo (FR-003)
- [ ] T034 [US1] Implementar en `Session` los comandos generales: `start` (sin corrida: nueva `Run`, `world.reset_to_start()`, `robot.reset()`, motores a 0, `rng` de `[seed, n]`, `world.begin_run`, `event run_started`; con corrida `run_active`), `stop` (`event run_finished`; sin corrida `no_run`), `set_config` (se aplica y se responde con `config` al inicio del paso en que se procesa, FR-032; el robot usa la config nueva desde su siguiente tick de control, que con `control_period_ms` mayor a 2 ms puede caer unos pasos después, FR-027; con corrida marca `config_changed`), `set_rate` (reinicia calendario, responde `config`), `list` (`catalog` con robots y pistas del catálogo + pistas de la sesión), `reset` (sin corrida: robot a la salida, sin respuesta; con corrida `run_active`); `event lap` por cada `LapCompleted` y, ante `OffTrack`, `event off_track` → `event run_finished` → telemetría del paso ya con `running = false`; todo rechazo responde `error` vía `commands.error_message` sin efecto; los comandos solo-sim (`load`, `set_profile`, `load_track`) responden `run_active` con corrida; sin corrida, hasta que US2 los implemente, no producen ningún mensaje ni efecto y se registra un WARNING en el log ("comando no implementado todavía"), sin inventar respuestas fuera del contrato (spec, Assumptions) (FR-021 a FR-032; hace pasar T020)
- [ ] T035 [US1] Implementar `src/velocista_sim/server/pacer.py`: `Pacer(session, clock)` asíncrono con la tanda de pasos y el ajuste de `t_base` de research R11, `asyncio.sleep` hasta el próximo paso de telemetría o 5 ms (lo menor), y `OutboundQueue` con descarte de `telemetry` (> 25 pendientes) y cierre 1008 si el backlog no descartable supera 1.000 (hace pasar T022)
- [ ] T036 [US1] Implementar `src/velocista_sim/server/app.py`: `create_app(settings=None, clock=None) -> FastAPI` que carga el catálogo al crear la app (falla si es inválido) y define `/ws`: acepta, crea `Session` (parámetros de conexión `robot`/`track` leídos pero con los por defecto si faltan), envía `open()`, lanza las tareas Pacer, Sender y lector de frames (`submit`), y al desconectarse cancela todo y descarta la sesión sin `run_finished` (FR-001, FR-026; hace pasar T021; depende de T033–T035)
- [ ] T037 [US1] Reemplazar `main()` en `src/velocista_sim/__init__.py` por el arranque de uvicorn con `create_app(Settings.from_env(os.environ))`, `host "0.0.0.0"`, `port = settings.port` y `proxy_headers=True` (research R14), para que `uv run velocista-sim` sirva `/ws` en local

**Checkpoint**: US1 completa. `uv run pytest` en verde y quickstart §2 (`uv run velocista-sim` + un cliente WebSocket cualquiera) da 3 vueltas y el `summary`. Es el MVP para el optimizador, solo en local: hasta terminar US2, `load`, `set_profile` y `load_track` sin corrida no responden (avisar al equipo que no los use) y no se despliega (T050 va después de la Phase 4).

---

## Phase 4: User Story 2 - Cambiar de robot, ajustar el perfil y cargar otra pista (Priority: P2)

**Goal**: comandos solo-sim `load`, `set_profile`, `load_track` y parámetros de conexión
`robot`/`track`.

**Independent Test**: en una sesión sin corrida, `load_track` con `oval-small`, `set_profile`
con un valor medido y `load` de `velocista-01`; comprobar las respuestas y que una corrida
posterior usa la pista y el perfil nuevos (quickstart §3).

### Tests de User Story 2 ⚠️

- [ ] T038 [P] [US2] Agregar a `tests/integration/test_session_core.py` los casos sin E/S de US2: `load velocista-01` → `hello` + `config`, conserva config, `rate_hz` y pista, borra los `measured` previos y deja el robot en la salida; `load` inexistente → `unknown_robot`; `set_profile {"wheelbase_m": 0.128}` → `config` y la física usa el nuevo valor (el giro cambia); `set_profile` con `null` borra el medido; `set_profile` con parámetro de `hello` (`line_sensors`), inexistente, tipo incorrecto o fuera de rango → `invalid_params`/`out_of_range` sin cambiar nada (todo o nada); `load_track oval-small` → `config` con `track_id "oval-small"`, robot en su salida y `list` la incluye; pista inválida → `invalid_track` y la pista vigente sigue; SC-005 con un PID bueno en `oval-small` (con corte): ≥ 1 vuelta sin `off_track`; `load`, `set_profile`, `load_track` y `reset` con corrida → `run_active` sin efecto (SC-007)
- [ ] T039 [P] [US2] Escribir `tests/integration/test_ws_sim_only.py` con `TestClient` y `ContractClient`: escenarios de aceptación US2-1 a US2-8 por WebSocket, incluida la conexión con `?robot=no-existe&track=no-existe` → `hello` y `config` por defecto y luego `error unknown_robot` y `error unknown_track` en ese orden, con la conexión abierta; validar que todo mensaje posterior a un `load` se valida contra el `hello` nuevo; reproducir la secuencia de quickstart §3 y comprobar las respuestas en orden

### Implementación de User Story 2

- [ ] T040 [US2] Implementar `load` en `Session` (`src/velocista_sim/server/session.py`): sin corrida, con `robot_id` del catálogo, reemplaza el perfil (sin `measured` previos), recalcula `effective`, reconstruye `WorldParams`/`RobotParams` con `set_params`, reinicia el calendario de control, deja el robot en la salida y emite `hello` + `config`; registra el perfil efectivo en el log INFO; ID fuera del catálogo → `unknown_robot` (FR-033)
- [ ] T041 [US2] Implementar `set_profile` en `Session` (`src/velocista_sim/server/session.py`): sin corrida, aplica todo o nada los `measured` (valor fija, `null` borra) sobre una copia del perfil, valida el resultado con `validate_profile` antes de aplicarlo, actualiza `effective` y los parámetros de mundo y robot sin mover el robot, responde `config` y registra el perfil efectivo en el log (FR-034, principio V)
- [ ] T042 [US2] Implementar `load_track` en `Session` (`src/velocista_sim/server/session.py`): sin corrida, construye `TrackGeometry.from_track` de la pista ya validada por `commands.parse`, la agrega a `session_tracks` (mismo `id` reemplaza), la deja vigente, robot en su salida, responde `config` con el nuevo `track_id`; `list` incluye las pistas de la sesión (FR-035)
- [ ] T043 [US2] Implementar los parámetros de conexión en `Session.open()` y `/ws` (`src/velocista_sim/server/session.py`, `src/velocista_sim/server/app.py`): `robot` y `track` del query string eligen perfil y pista iniciales; si no existen se usan los por defecto y se emiten tras `hello` + `config` los `error` `unknown_robot` y/o `unknown_track` (en ese orden), sin cerrar la conexión (FR-037; hace pasar T038, T039)

**Checkpoint**: US1 y US2 funcionan; quickstart §3 da las respuestas esperadas.

---

## Phase 5: User Story 3 - Servicio público y cliente de ejemplo (Priority: P3)

**Goal**: `/health`, límite de sesiones, imagen Docker, despliegue en Railway y
`examples/client.py`.

**Independent Test**: desde otra máquina, `curl https://<proyecto>.up.railway.app/health` da 200
y `uv run <url-raw>/examples/client.py wss://<proyecto>.up.railway.app/ws` imprime el `summary`
(quickstart §4).

### Tests de User Story 3 ⚠️

- [ ] T044 [P] [US3] Escribir `tests/integration/test_health_client.py`: `GET /health` con `TestClient` → 200 `{"status": "ok", "sessions": n, "max_sessions": m}` y, con `max_sessions = 1` y una sesión abierta, 503 `{"status": "full", …}` y una segunda conexión a `/ws` se cierra con código 1013 sin mensajes; desconexión durante una corrida: abrir `/ws`, enviar `start`, cerrar la conexión y comprobar que `/health` vuelve a `sessions = 0` (la sesión y sus tareas se liberan, FR-026); levantar uvicorn real en un puerto libre (fixture con hilo o subproceso) y ejecutar `examples/client.py` con `subprocess.run([sys.executable, "examples/client.py", …])` usando el intérprete del venv de dev (que ya tiene `websockets` por T001), nunca con `uv run`, para no resolver el entorno PEP 723 ni necesitar red (`--laps 1 --timeout 20`): código de salida 0 y `summary` impreso con `laps`; con `--kp 0 --kd 0` imprime `off_tracks 1`; con una URL sin servidor sale con código 1 y mensaje en español

### Implementación de User Story 3

- [ ] T045 [US3] Agregar a `src/velocista_sim/server/app.py` el conteo de sesiones activas, `GET /health` según contracts/http-health.md (200 `ok` / 503 `full` con `sessions` y `max_sessions`, sin esperar a la simulación) y el cierre inmediato con código 1013 de las conexiones nuevas a `/ws` cuando `sessions ≥ max_sessions` (FR-042, research R14)
- [ ] T046 [P] [US3] Crear `examples/client.py` según contracts/client-cli.md: metadatos PEP 723 (`requires-python >= 3.12`, `dependencies = ["websockets>=15"]`), argumentos `URL` (defecto `ws://localhost:8000/ws`), `--kp 0.045`, `--ki 0`, `--kd 0.9`, `--base-speed 180`, `--laps 3`, `--timeout 30`, `--robot`, `--track`; muestra `hello` y `config` en una línea cada uno, envía `set_config` (si llega `error`, lo muestra y sale con código 2), envía `start`, muestra cada `event`, envía `stop` tras `--laps` vueltas o `--timeout` s salvo `off_track`, imprime el `summary` legible (vueltas, mejor y promedio en s, salidas de pista, pista, config, `config_changed`) y sale con 0; errores de conexión: mensaje en español y código 1; ignora `sim_truth` y mensajes desconocidos (FR-043)
- [ ] T047 [P] [US3] Crear `Dockerfile` sobre `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`: copia `pyproject.toml`, `uv.lock`, `README.md`, `src/`, `contract/` y `config/`, ejecuta `uv sync --locked --no-dev` y usa `CMD ["uv", "run", "--no-sync", "velocista-sim"]`; y `.dockerignore` que excluye `.venv/`, `.git/`, `.pytest_cache/`, `__pycache__/`, `specs/`, `tests/`, `.claude/`, `.specify/` (research R14)
- [ ] T048 [P] [US3] Crear `railway.json` con builder `DOCKERFILE`, `healthcheckPath "/health"` y política de reinicio `ON_FAILURE` (research R14)
- [ ] T049 [US3] Verificar la imagen en local según quickstart §4 (`docker build -t velocista-sim .`, `docker run --rm -e PORT=9000 -p 9000:9000 velocista-sim`, `uv run examples/client.py ws://localhost:9000/ws`) y corregir `Dockerfile` si algo falla (depende de T045–T048)
- [ ] T050 [US3] Desplegar en Railway (tarea manual del responsable del proyecto): conectar el repo, generar dominio público en *Settings → Networking* y comprobar desde otra máquina `curl https://<proyecto>.up.railway.app/health` y `uv run https://raw.githubusercontent.com/<org>/velocista-sim/main/examples/client.py wss://<proyecto>.up.railway.app/ws` (FR-041, SC-006)
- [ ] T051 [US3] Agregar al `README.md` una sección "Simulador" en español: cómo correrlo en local (`uv run velocista-sim`), variables de entorno (`PORT`, `VELOCISTA_SEED`, `VELOCISTA_MAX_SESSIONS`, `VELOCISTA_CONFIG_DIR`), URL pública `wss://<proyecto>.up.railway.app/ws`, `/health` y el uso de `examples/client.py` sin clonar el repo

**Checkpoint**: las tres historias funcionan; los compañeros usan la URL pública.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: criterios transversales que necesitan todas las historias.

- [ ] T052 [P] Escribir `tests/slow/test_realtime_rate.py` con `@pytest.mark.slow`: uvicorn real con reloj del sistema, 5 sesiones simultáneas durante 10 s; la frecuencia media de `telemetry` de cada sesión tiene desvío < 5 % respecto de `rate_hz` (SC-004); ejecutar con `uv run pytest -m slow`
- [ ] T053 [P] Escribir `tests/integration/test_message_coverage.py` como test autónomo, que no depende del orden ni de otros tests ni de un registro global (funciona igual con `-k` o `-m`): corre un guion fijo sobre el núcleo `Session` (abrir, `list`, `set_config`, `set_rate`, `start`, vueltas, `stop`, una corrida con `kp 0` hasta `off_track`, y un frame por cada rechazo) y una conexión `/ws` con `?robot=no-existe&track=no-existe`; pasa cada mensaje por un `MessageChecker` propio y comprueba que se emitieron y validaron todos los `type` (`hello`, `config`, `telemetry`, `event`, `catalog`, `error`), todos los `event` (`run_started`, `lap`, `off_track`, `run_finished`) y todos los `code` del contrato salvo `sim_only` (`invalid_json`, `unknown_cmd`, `invalid_params`, `out_of_range`, `run_active`, `no_run`, `unknown_robot`, `unknown_track`, `invalid_track`, `unsupported_version`) (research R10, SC-002)
- [ ] T054 [P] Escribir un test de rendimiento rápido en `tests/unit/test_world_performance.py`: el núcleo `Session` ejecuta 5.000 pasos con corrida activa en `oval-01` y se informa la tasa; fallar si queda por debajo de 2.500 pasos/s, que es el **mínimo** para sostener 5 sesiones en tiempo real en un núcleo (5 × 500 pasos/s, SC-004), no un margen; el objetivo del plan (≥ 10.000 pasos/s) solo se informa en la salida del test, no se exige, para no ser frágil en CI
- [ ] T055 Revisar que todos los docstrings, comentarios y `error.message` de `src/velocista_sim/world/`, `src/velocista_sim/robot/` y `src/velocista_sim/server/` estén en español y los identificadores en inglés (constitución, flujo de desarrollo)
- [ ] T056 Ejecutar la validación completa de [quickstart.md](./quickstart.md) §1–§3 (`uv sync --locked`, `uv run pytest`, `uv run pytest -m slow`, servidor local + cliente con config buena y mala, comandos solo-sim a mano) y anotar cualquier desvío

---

## Dependencies & Execution Order

### Dependencias entre fases

- **Setup (Phase 1)**: sin dependencias.
- **Foundational (Phase 2)**: depende de Setup; BLOQUEA todas las historias.
- **US1 (Phase 3)**: depende de Foundational. Es el MVP.
- **US2 (Phase 4)**: depende de US1 (extiende `Session` y `/ws`; necesita mundo, robot y corridas
  para verificar que una corrida posterior usa el perfil y la pista nuevos).
- **US3 (Phase 5)**: depende de US1 (necesita `/ws` y `main()`); no depende de US2, pero la spec
  pide implementar P2 antes de desplegar (Assumptions), así que T050 va después de la Phase 4.
  T044–T048 se pueden adelantar en paralelo con US2.
- **Polish (Phase 6)**: depende de todas las historias (T053 necesita los errores de US2).

### Dependencias dentro de US1

- Tests T014–T022 primero (todos [P], archivos distintos).
- `world`: T023 → T025 → T026 → T028; T027 en paralelo con T025/T026.
- `robot`: T024 → T029, T030 (paralelas) → T031. La rama `robot` es independiente de la rama
  `world`.
- `server`: T032 → T033 → T034 (necesitan T028 y T031) → T035 → T036 → T037.

### Dependencias dentro de US2 y US3

- US2: T038, T039 → T040 → T041 → T042 → T043 (mismo archivo `session.py`: en serie).
- US3: T044 → T045; T046, T047, T048 en paralelo; T049 después de T045–T048; T050 después de
  T049 y de la Phase 4; T051 al final.

### Oportunidades de paralelismo

- Setup: T003 y T004.
- Foundational: T005, T006, T007, T008, T009, T011 y T012 en paralelo; luego T010 y T013.
- US1: los nueve tests; T023/T024; las ramas `world` y `robot` completas en paralelo.
- US3: T046, T047, T048.
- Polish: T052, T053, T054.

---

## Parallel Example: User Story 1

```text
# Todos los tests de US1 a la vez:
Task: "T014 tests/unit/test_world_track.py"
Task: "T015 tests/unit/test_world_sensors.py"
Task: "T016 tests/unit/test_world_physics.py"
Task: "T017 tests/unit/test_world_detection.py"
Task: "T018 tests/unit/test_robot_line.py"
Task: "T019 tests/unit/test_robot_pid.py"
Task: "T020 tests/integration/test_session_core.py"
Task: "T021 tests/integration/test_ws_session.py"
Task: "T022 tests/unit/test_pacer.py"

# Luego, mundo y robot en paralelo:
Task: "T023 src/velocista_sim/world/params.py"     →  T025 → T026 → T028
Task: "T027 src/velocista_sim/world/physics.py"
Task: "T024 src/velocista_sim/robot/params.py"     →  T029 + T030 → T031
```

## Parallel Example: User Story 3

```text
Task: "T046 examples/client.py"
Task: "T047 Dockerfile + .dockerignore"
Task: "T048 railway.json"
```

---

## Implementation Strategy

### MVP primero (solo US1)

1. Phase 1: Setup.
2. Phase 2: Foundational (bloquea todo).
3. Phase 3: US1.
4. **PARAR Y VALIDAR**: `uv run pytest` y quickstart §2 con `uv run velocista-sim`. El
   optimizador ya puede hacer `set_config` → `start` → `run_finished` contra un servidor local
   (es la entrega de mañana).

### Entrega incremental

1. Setup + Foundational → base lista.
2. US1 → tests en verde → demo local (MVP).
3. US2 → `load`, `set_profile`, `load_track` → quickstart §3.
4. US3 → `/health`, cliente de ejemplo, Docker, Railway → URL pública para el equipo.
5. Polish → SC-004 (tiempo real), cobertura de mensajes, rendimiento.

### Equipo en paralelo

Tras Foundational: una persona en la rama `world` (T023, T025–T028), otra en la rama `robot`
(T024, T029–T031) y otra en los tests de integración (T020–T022) y en `examples/client.py`
(T046, que solo depende del contrato). El `server` (T032–T037) une ambas ramas.

---

## Notes

- [P] = archivos distintos, sin dependencias pendientes.
- [Story] vincula cada tarea a su historia para trazabilidad.
- Verificar que los tests fallan antes de implementar.
- Commits Conventional Commits con descripción en español (p. ej. `feat(world): agrega física diferencial`), uno por tarea o grupo lógico.
- Ningún mensaje nuevo ni campo nuevo: si una tarea parece requerir cambiar el contrato, parar y revisar (principio I).
