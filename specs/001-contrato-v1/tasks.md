---
description: "Lista de tareas para implementar el contrato v1"
---

# Tasks: Contrato v1 de mensajes entre velocista-sim y sus clientes

**Input**: documentos de diseño en `specs/001-contrato-v1/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/validator-api.md](./contracts/validator-api.md),
[contracts/example-format.md](./contracts/example-format.md), [quickstart.md](./quickstart.md)

**Tests**: se incluyen. La constitución (principio VII) exige tests que validen los mensajes, y
los criterios SC-001, SC-002 y SC-005 son verificaciones automáticas. En este contrato los
ejemplos de `contract/examples/` **son** los casos de prueba: `tests/contract/test_examples.py`
los descubre solo, así que agregar un ejemplo agrega un test.

**Organization**: tareas agrupadas por historia de usuario (US1 a US4 de la spec).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia de usuario a la que pertenece la tarea (US1…US4)

## Convenciones comunes a todas las tareas

- Identificadores en inglés; textos (`description`, `Violation.message`, docstrings, contrato) en español.
- Todo archivo se lee y escribe en **UTF-8** (`encoding="utf-8"`), JSON con indentación de 2 espacios.
- Todo schema declara `"$schema": "https://json-schema.org/draft/2020-12/schema"` y un `$id`
  absoluto `https://velocista-sim.local/contract/v1/<ruta relativa a contract/schemas/>`
  (p. ej. `https://velocista-sim.local/contract/v1/messages/telemetry.schema.json`). Las piezas
  comunes se referencian con `$ref` relativo, p. ej. `"../common.schema.json#/$defs/pwm"` (research R2).
- **Ningún** schema restringe `additionalProperties` (research R4, FR-005).
- Ejemplos: envoltorio `{"description", "hello"?, "message", "expected"?}` según
  [example-format.md](./contracts/example-format.md); `expected` es una lista de `{"rule", "path"}` y
  solo existe en `invalid/`. Cada ejemplo inválido debe fallar **exactamente** por sus `expected`.
- `rule` para errores de schema = palabra clave de JSON Schema que falla (`required`, `maximum`,
  `type`, `enum`, `const`, `minItems`, `not`, `anyOf`, …); para reglas propias = identificador de
  [data-model.md](./data-model.md#reglas-de-validación).
- `path` = JSON Pointer dentro de `message`. Para `required`, el pointer apunta a la propiedad que
  falta (p. ej. `/seq`), no al objeto que la contiene.
- Los ejemplos tomados del PDF llevan `description` que empieza por `"PDF v1.1:"` (SC-003).
- Commits en Conventional Commits con descripción en español (p. ej. `feat(contract): …`,
  `test(contract): …`, `docs(contract): …`).

---

## Phase 1: Setup (infraestructura compartida)

**Purpose**: dependencias, configuración de pytest, CI y estructura de carpetas.

- [ ] T001 Mover `jsonschema` de dependencia de desarrollo a dependencia de ejecución con `uv remove --dev jsonschema` y `uv add jsonschema` (research R1); verificar que `pyproject.toml` lo lista en `[project].dependencies`, que `uv.lock` se actualiza y que `pytest` sigue en el grupo `dev`
- [ ] T002 Agregar a `pyproject.toml` la sección `[tool.pytest.ini_options]` con `testpaths = ["tests"]` y `addopts = "-ra"` (research R11)
- [ ] T003 [P] Crear `.github/workflows/tests.yml`: nombre `tests`, disparado en `push` y `pull_request`, job en `ubuntu-latest` con los pasos `actions/checkout@v5`, `astral-sh/setup-uv@v6` (con `enable-cache: true`), `uv sync --locked` y `uv run pytest` (research R10)
- [ ] T004 [P] Crear la estructura de carpetas vacía con `.gitkeep` donde haga falta: `contract/schemas/messages/`, `contract/schemas/commands/`, `contract/examples/valid/`, `contract/examples/invalid/`, `src/velocista_sim/contract/`, `tests/contract/`, `tests/unit/`

---

## Phase 2: Foundational (prerrequisitos bloqueantes)

**Purpose**: el núcleo que comparten todas las historias: piezas comunes de schema, carga de
schemas, tipos de resultado, despacho por `type`/`cmd` y el runner genérico de ejemplos.

**⚠️ CRITICAL**: ninguna historia puede empezar antes de terminar esta fase.

- [ ] T005 Crear `contract/schemas/common.schema.json` con estos `$defs` (data-model.md § `$defs`): `envelope` (objeto con `type` string, `v` `{"const": 1}`, `t_ms` entero `minimum: 0`; los tres en `required`); `command_envelope` (`cmd` string obligatorio, `v` `{"const": 1}` opcional); `run_id` (string `minLength: 1`); `pwm` (entero `minimum: -255`, `maximum: 255`); `base_speed` (entero 0…255); `rate_hz` (entero 10…100); `pid_params` (objeto con `kp`, `ki`, `kd` número `minimum: 0`, los tres `required`); `controller_config` (objeto con `controller` `{"enum": ["pid"]}`, `params` → `pid_params`, `base_speed` → `base_speed`; los tres `required`); `track_id` (`{"type": ["string", "null"], "minLength": 1}`); `error_code` (`enum` con exactamente `invalid_json`, `unknown_cmd`, `invalid_params`, `out_of_range`, `sim_only`, `run_active`, `no_run`, `unknown_robot`, `unknown_track`, `invalid_track`, `unsupported_version`)
- [ ] T006 [P] Crear `src/velocista_sim/contract/result.py` con las dataclasses congeladas `Violation(rule: str, path: str, message: str)` y `ValidationResult(violations: tuple[Violation, ...], context_checked: bool)` con la propiedad `ok` (`True` si no hay violaciones); el orden de `violations` es estable, ordenado por `path` y luego por `rule` (validator-api.md § Garantías)
- [ ] T007 [P] Crear `src/velocista_sim/contract/schemas.py` con `load_schemas(schema_dir: Path | None = None)`: recorre `**/*.schema.json` de la carpeta (por defecto `contract/schemas/`, encontrada subiendo desde `Path(__file__)` hasta hallar un directorio que contenga `contract/schemas`; si no la encuentra, `FileNotFoundError` con mensaje en español), lee cada archivo en UTF-8, construye un `referencing.Registry` indexado por `$id` (`Resource.from_contents` con draft 2020-12) y devuelve un objeto que permite pedir el schema por ruta relativa (`"messages/telemetry"`); cachear el resultado por carpeta con `functools.cache` (research R2, R6)
- [ ] T008 Crear `src/velocista_sim/contract/validate.py` (depende de T006 y T007) con `validate_message`, `validate_command`, `validate_profile` y `validate_track` según [validator-api.md](./contracts/validator-api.md), implementando por ahora solo la capa de schema: (a) si la entrada no es `dict` → `Violation("type", "", …)`; (b) `validate_message` lee `type` y aplica `messages/<type>.schema.json`; si `type` falta o no hay schema → `Violation("unknown_type", "/type", …)`; (c) `validate_command` lee `cmd` y aplica `commands/<cmd>.schema.json`; si falta o es desconocido → `Violation("unknown_cmd", "/cmd", …)`; (d) `validate_profile` aplica `robot-profile.schema.json` y `validate_track` aplica `track.schema.json`; (e) usa `Draft202012Validator(schema, registry=…, format_checker=Draft202012Validator.FORMAT_CHECKER)` y convierte cada error de `iter_errors` (sin aplanar `error.context`: un fallo de `anyOf` se informa como `anyOf`; los de `if`/`then`/`else` y `allOf` ya llegan como el error interno) en `Violation(rule=error.validator, path=<JSON Pointer de error.absolute_path>, message=<texto en español>)`, y para `required` agrega al pointer el nombre de la propiedad que falta; (f) deja ganchos vacíos `_context_violations(message, hello)` (capa 2) y `_track_violations(track)` (capa 3) que devuelven `[]`; (g) `context_checked = hello is not None or message.get("type") == "hello"`; si el mensaje es un `hello`, se usa a sí mismo como contexto
- [ ] T009 Crear `src/velocista_sim/contract/__init__.py` que reexporta `Violation`, `ValidationResult`, `load_schemas`, `validate_message`, `validate_command`, `validate_profile`, `validate_track` (y `effective_profile` cuando exista, en T044), con `__all__` explícito
- [ ] T010 [P] Crear `tests/conftest.py` con utilidades compartidas: `EXAMPLES_DIR = <raíz del repo>/contract/examples`; `load_example(path)` que lee el envoltorio en UTF-8 y resuelve `hello` (si es string, carga `valid/hello/<nombre>.json` y toma su `message`; si es objeto, lo usa tal cual; si falta, `None`); `validator_for(path)` que elige la función según la carpeta: `hello|config|telemetry|event|catalog|error` → `validate_message(message, hello)`, `commands/<cmd>` → `validate_command`, `robot-profile` → `validate_profile`, `track` → `validate_track`
- [ ] T011 [P] Crear `tests/contract/test_schemas.py`: para cada `contract/schemas/**/*.schema.json`, verificar que `Draft202012Validator.check_schema` pasa, que el `$id` coincide con `https://velocista-sim.local/contract/v1/<ruta relativa>` y que todos los `$ref` se resuelven en el registro de `load_schemas()`; verificar también que ningún schema declara `additionalProperties: false`
- [ ] T012 Crear `tests/contract/test_examples.py` (depende de T010): un test parametrizado por cada archivo de `contract/examples/valid/**/*.json` (id = ruta relativa) que exige `result.ok`, y otro por cada archivo de `contract/examples/invalid/**/*.json` que exige que el conjunto de pares `(rule, path)` de `result.violations` sea **igual** al de `expected`; ambos validan además que el envoltorio tenga `description` no vacía y que `expected` exista solo en `invalid/` y no esté vacío
- [ ] T013 [P] Crear `contract/contract-v1.md` con el esqueleto normativo en español: título y revisión **1.2** (protocolo `v = 1`); propósito; § Conexión (WebSocket único en `/ws`, parámetros `robot` y `track`, sesión por conexión, desconexión y keepalive según FR-007/FR-007a); § Formato (un mensaje JSON UTF-8 por frame, envoltorio `type`/`v`/`t_ms`, comandos con `cmd` y `v` opcional, FR-009 a FR-011); § Unidades, con la tabla de excepciones no SI (tiempo en ms, ADC crudo, `line_position` en milésimas de sensor, PWM −255…255, FR-012); § Versionado (FR-005, campos desconocidos se ignoran, research R4); § Elementos solo-sim (`sim_truth`, `reset`, `load`, `set_profile`, `load_track`); § Cambios respecto del PDF v1.1 (research R9: `capabilities.lap_timing`, `capabilities.battery.voltage_sense`, `error.code`, `error.cmd`, `summary.config_changed`, forma unificada de `summary.config`, `v` obligatorio en `event`, `hello` reenviado tras `load` (único comando que cambia datos de `hello`), `set_profile` limitado a parámetros físicos y de calibración, `capabilities.motors` fijo en 2, valores de `source` del perfil en inglés (`defined`, `datasheet`, `estimated`, `current_robot`; el PDF usaba `"estimado"`), campos condicionados obligatorios cuando su capacidad está declarada, `summary.laps` no nulo con `lap_timing = true` y `best_lap_ms`/`avg_lap_ms` coherentes con `laps`, origen de coordenadas de la pista y tolerancia de muestreo ±10 %); secciones vacías con encabezado para Mensajes, Comandos, Perfil del robot y Pista track v1, que completan las historias; nota de que `contract/contrato-v1.1-velocista-sim.pdf` queda solo como referencia histórica

**Checkpoint**: `uv run pytest` pasa (sin ejemplos aún, solo `test_schemas.py` sobre `common.schema.json`). Las historias pueden empezar.

---

## Phase 3: User Story 1 - Desarrollar un cliente contra el contrato sin el simulador (Priority: P1) 🎯 MVP

**Goal**: schemas, ejemplos y validación de los 6 mensajes servidor→cliente, incluidas las reglas
contextuales de los sensores de línea.

**Independent Test**: `uv run pytest tests/contract -k "examples and (hello or config or telemetry or event or catalog or error)"`: todos los ejemplos válidos se aceptan y cada inválido falla por su `expected` (escenarios US1-1 a US1-5).

### Schemas de mensajes

- [ ] T014 [P] [US1] Crear `contract/schemas/messages/hello.schema.json`: `allOf` con `common#/$defs/envelope`; `type` `{"const": "hello"}`; obligatorios `session_id` (string `minLength: 1`), `source` (`{"enum": ["sim", "robot"]}`), `robot` (objeto con `id`, `firmware`, `hw_rev`: string `minLength: 1`, los tres obligatorios) y `capabilities` (objeto con, todos obligatorios: `line_sensors` entero `minimum: 1`; `adc_bits` entero `minimum: 8`, `maximum: 16`; `motors` `{"const": 2}` (fijo en v1); `turbine`, `encoders`, `imu`, `lap_timing` booleanos; `battery` objeto con `cells` entero `minimum: 1`, `nominal_v` número `exclusiveMinimum: 0` y `voltage_sense` booleano, los tres obligatorios) (FR-013)
- [ ] T015 [P] [US1] Crear `contract/schemas/messages/config.schema.json`: envelope; `type` `{"const": "config"}`; obligatorios `controller` (`{"enum": ["pid"]}`), `params` (`common#/$defs/pid_params`), `base_speed` (`common#/$defs/base_speed`, "entero, PWM 0–255"), `rate_hz` (`common#/$defs/rate_hz`, "entero 10–100") y `track_id` (`common#/$defs/track_id`, "string, o null si no hay pista") (FR-015)
- [ ] T016 [P] [US1] Crear `contract/schemas/messages/telemetry.schema.json`: envelope; `type` `{"const": "telemetry"}`; obligatorios `seq` (entero `minimum: 0`), `running` (booleano), `sensors` (array `minItems: 1` de enteros `minimum: 0`, `maximum: 65535`), `line_position` (entero `minimum: 0`), `line_lost` (booleano), `error` (entero), `control` (objeto con `p`, `i`, `d`, `out` números, los cuatro obligatorios) y `motors` (objeto con `left`, `right` → `common#/$defs/pwm`, ambos obligatorios); opcionales `run_id` (`common#/$defs/run_id`), `lap` (objeto con `n` entero `minimum: 0` y `current_ms` entero `minimum: 0`, ambos obligatorios), `battery_v` (número `exclusiveMinimum: 0`), `odometry` (objeto con `distance_m` número `minimum: 0`, `speed_mps` número, `heading_rad` número; ninguno obligatorio; `minProperties: 1`) y `sim_truth` (objeto con `x`, `y`, `theta`, `speed_mps`, `distance_m` números, los cinco obligatorios); condicionales: `if {"properties": {"running": {"const": true}}} then {"required": ["run_id"]} else {"allOf": [{"not": {"required": ["run_id"]}}, {"not": {"required": ["lap"]}}]}` (FR-018 a FR-020; data-model.md capa 1)
- [ ] T017 [P] [US1] Crear `contract/schemas/messages/event.schema.json`: envelope; `type` `{"const": "event"}`; obligatorios `event` (`{"enum": ["run_started", "lap", "off_track", "run_finished"]}`) y `run_id`; `$defs` y `allOf` de `if`/`then` por subtipo: `lap` → obligatorios `lap` (entero `minimum: 1`) y `lap_ms` (entero `exclusiveMinimum: 0`); `off_track` → obligatorio `reason` (`{"enum": ["line_lost"]}`); `run_finished` → obligatorio `summary` con, todos obligatorios: `laps` (entero `minimum: 0` o `null`), `best_lap_ms` y `avg_lap_ms` (entero `exclusiveMinimum: 0` o `null`), `off_tracks` (entero `minimum: 0`), `track_id` (`common#/$defs/track_id`), `config` (`common#/$defs/controller_config`) y `config_changed` (booleano); dentro de `summary`, `if {"properties": {"laps": {"enum": [0, null]}}} then` `best_lap_ms` y `avg_lap_ms` `{"const": null}` `else` `best_lap_ms` y `avg_lap_ms` `{"type": "integer", "exclusiveMinimum": 0}` ("entero > 0 si `laps ≥ 1`; `null` si `laps` es `0` o `null`") (FR-022, FR-023, FR-025; research R3)
- [ ] T018 [P] [US1] Crear `contract/schemas/messages/catalog.schema.json`: envelope; `type` `{"const": "catalog"}`; obligatorios `robots` y `tracks` (arrays de string `minLength: 1`, `uniqueItems: true`) (FR-026)
- [ ] T019 [P] [US1] Crear `contract/schemas/messages/error.schema.json`: envelope; `type` `{"const": "error"}`; obligatorios `code` (`common#/$defs/error_code`) y `message` (string `minLength: 1`); opcional `cmd` (string `minLength: 1`) (FR-027)

### Ejemplos válidos

- [ ] T020 [P] [US1] Crear `contract/examples/valid/hello/sim-default.json` con el `hello` del PDF agregando `capabilities.battery.voltage_sense: true` y `capabilities.lap_timing: true` (description "PDF v1.1: …"), y `contract/examples/valid/hello/robot-real.json` con `robot.id: "velocista-01"` (debe coincidir con `valid/catalog/robot-real.json`, T054), `source: "robot"`, `firmware` de ejemplo, `voltage_sense: false` y `lap_timing: false`
- [ ] T021 [P] [US1] Crear `contract/examples/valid/config/pdf-config.json` (config del PDF; `hello: "sim-default"`)
- [ ] T022 [P] [US1] Crear en `contract/examples/valid/telemetry/`: `pdf-robot-actual.json` (telemetry del PDF, `hello: "sim-default"`; verificar `error = 7342 − 7500 = −158`), `idle-no-run.json` (`hello: "sim-default"`, `running: false`, sin `run_id` ni `lap`, con `sim_truth` y `battery_v`) y `unknown-field.json` (el telemetry del PDF con un campo extra `"foo": 1`, `hello: "sim-default"`, escenario US1-5). Con `hello: "sim-default"` todo `telemetry` MUST traer `sim_truth` y `battery_v`, y además `lap` si `running = true` (reglas `*_missing`, T052)
- [ ] T023 [P] [US1] Crear en `contract/examples/valid/event/` los 4 eventos del PDF agregando `"v": 1`: `pdf-run-started.json`, `pdf-lap.json`, `pdf-off-track.json` y `pdf-run-finished.json`, este último con `summary.config` en forma `{"controller": "pid", "params": {"kp": 0.045, "ki": 0, "kd": 0.9}, "base_speed": 180}` y `"config_changed": false` (research R9); todos con `hello: "sim-default"`
- [ ] T024 [P] [US1] Crear `contract/examples/valid/catalog/pdf-catalog.json` y `contract/examples/valid/error/pdf-error.json` (error del PDF con `"code": "sim_only"` y `"cmd": "load_track"`)

### Ejemplos inválidos (capa de schema)

- [ ] T025 [P] [US1] Crear en `contract/examples/invalid/telemetry/`: `missing-seq.json` (`required` en `/seq`), `sensor-above-16-bits.json` (sensor 70000 → `maximum` en `/sensors/0`), `motor-pwm-out-of-range.json` (`left: 300` → `maximum` en `/motors/left`), `running-without-run-id.json` (`required` en `/run_id`) y `run-id-while-idle.json` (`running: false` con `run_id` → `not` en `""`); todos sin `hello` para que no intervengan reglas contextuales
- [ ] T026 [P] [US1] Crear inválidos de envoltorio y de los demás mensajes: `contract/examples/invalid/hello/bad-source.json` (`source: "real"` → `enum` en `/source`), `contract/examples/invalid/hello/wrong-version.json` (`v: 2` → `const` en `/v`), `contract/examples/invalid/config/rate-too-low.json` (`rate_hz: 5` → `minimum` en `/rate_hz`), `contract/examples/invalid/event/lap-missing-lap-ms.json` (`required` en `/lap_ms`), `contract/examples/invalid/event/run-finished-missing-config-changed.json` (`required` en `/summary/config_changed`), `contract/examples/invalid/catalog/robots-not-array.json` (`type` en `/robots`), `contract/examples/invalid/error/unknown-code.json` (`code: "boom"` → `enum` en `/code`), `contract/examples/invalid/error/negative-t-ms.json` (`t_ms: -1` → `minimum` en `/t_ms`), `contract/examples/invalid/error/missing-message.json` (`required` en `/message`), `contract/examples/invalid/catalog/missing-tracks.json` (`required` en `/tracks`), `contract/examples/invalid/config/missing-track-id.json` (`required` en `/track_id`), `contract/examples/invalid/config/rate-not-integer.json` (`rate_hz: 50.5` → `type` en `/rate_hz`), `contract/examples/invalid/hello/three-motors.json` (`capabilities.motors: 3` → `const` en `/capabilities/motors`), `contract/examples/invalid/hello/adc-bits-too-high.json` (`adc_bits: 20` → `maximum` en `/capabilities/adc_bits`), `contract/examples/invalid/hello/missing-capabilities.json` (`required` en `/capabilities`), `contract/examples/invalid/event/bad-off-track-reason.json` (`reason: "crash"` → `enum` en `/reason`), `contract/examples/invalid/event/lap-not-integer.json` (`lap: "3"` → `type` en `/lap`), `contract/examples/invalid/event/lap-ms-zero.json` (`lap_ms: 0` → `exclusiveMinimum` en `/lap_ms`) y `contract/examples/invalid/event/best-lap-null-with-laps.json` (`laps: 3`, `best_lap_ms: null` → `type` en `/summary/best_lap_ms`); todos sin `hello` (G1: cada schema con al menos un `required`, un `type` y, si tiene rangos, un fallo de rango)
- [ ] T027 [P] [US1] Crear `contract/examples/invalid/hello/unknown-type.json` (`type: "helo"` → `unknown_type` en `/type`) para cubrir el despacho de `validate_message`

### Validador contextual: sensores de línea

- [ ] T028 [US1] Crear `src/velocista_sim/contract/context_rules.py` con `context_violations(message: dict, hello: dict) -> list[Violation]` y, para `telemetry`, las reglas de data-model.md capa 2: `sensors_length` (en `/sensors`, si `len(sensors) ≠ capabilities.line_sensors`), `sensor_range` (en `/sensors/<i>`, por cada valor `> 2**adc_bits − 1`), `line_position_range` (en `/line_position`, si `line_position > (line_sensors − 1) × 1000`) y `error_consistency` (en `/error`, si `error ≠ line_position − (line_sensors − 1) × 500`); conectarlo al gancho `_context_violations` de `src/velocista_sim/contract/validate.py`; las reglas contextuales solo se evalúan si el mensaje pasó la capa de schema
- [ ] T029 [P] [US1] Crear en `contract/examples/invalid/telemetry/` (todos con `hello: "sim-default"` y partiendo del telemetry del PDF, que ya trae `sim_truth`, `battery_v` y `lap`, para que solo falle la regla indicada): `sensors-length.json` (15 valores → `sensors_length` en `/sensors`, escenario US1-4), `sensor-out-of-range.json` (valor 5000 en el índice 3 → `sensor_range` en `/sensors/3`, escenario US1-2), `line-position-out-of-range.json` (`line_position: 15001` y `error` coherente → `line_position_range` en `/line_position`) y `error-inconsistent.json` (`error: 0` con `line_position: 7342` → `error_consistency` en `/error`)
- [ ] T030 [P] [US1] Crear `tests/unit/test_context_rules.py` con casos unitarios de las 4 reglas de sensores, incluido un `hello` con `line_sensors: 8` (centro 3500) y `adc_bits: 10` (máximo 1023), y un caso que verifica que sin `hello` el resultado tiene `context_checked = False` y no informa reglas contextuales

### Contrato

- [ ] T031 [US1] Completar § Mensajes de `contract/contract-v1.md`: tabla de frecuencia y momento de envío de cada mensaje (FR-008, FR-013 —`hello` al conectarse y tras cada `load` aceptado; se interpreta todo con el último `hello`—, FR-016, FR-017, FR-026, FR-027) y, por mensaje, tabla de campos con tipo, unidad, rango y obligatoriedad copiada de la spec (FR-013 a FR-027, incluida la tabla de códigos de error), con enlace al schema y a los ejemplos; reglas de `seq` por sesión (FR-018) y de corrida (FR-025)

**Checkpoint**: US1 completa. Un cliente puede validar cualquier mensaje saliente del simulador sin tenerlo en marcha.

---

## Phase 4: User Story 2 - Controlar corridas y configuración igual en simulador y robot real (Priority: P2)

**Goal**: schemas y ejemplos de los 5 comandos generales, y ejemplos de la secuencia de corrida.

**Independent Test**: `uv run pytest tests/contract -k "examples and commands and (start or stop or set_config or set_rate or list)"` pasa; los ejemplos de `set_rate` cubren el escenario US2-6.

- [ ] T032 [P] [US2] Crear `contract/schemas/commands/start.schema.json`, `stop.schema.json` y `list.schema.json`: cada uno `allOf` con `common#/$defs/command_envelope` y `cmd` `{"const": "<nombre>"}`, sin otros campos (FR-029)
- [ ] T033 [P] [US2] Crear `contract/schemas/commands/set_config.schema.json`: command_envelope; `cmd` `{"const": "set_config"}`; opcionales `controller` (`{"enum": ["pid"]}`), `params` (objeto con `kp`, `ki`, `kd` número `minimum: 0`, ninguno obligatorio, `minProperties: 1`) y `base_speed` (`common#/$defs/base_speed`); `anyOf` de `{"required": ["controller"]}`, `{"required": ["params"]}`, `{"required": ["base_speed"]}` ("al menos uno") (FR-029; data-model.md capa 1)
- [ ] T034 [P] [US2] Crear `contract/schemas/commands/set_rate.schema.json`: command_envelope; `cmd` `{"const": "set_rate"}`; obligatorio `hz` → `common#/$defs/rate_hz` ("entero 10–100") (FR-029)
- [ ] T035 [P] [US2] Crear ejemplos válidos con los comandos del PDF: `contract/examples/valid/commands/start/pdf-start.json`, `.../stop/pdf-stop.json`, `.../list/pdf-list.json`, `.../set_config/pdf-set-config.json`, `.../set_config/only-base-speed.json`, `.../set_rate/pdf-set-rate.json` (`hz: 20`) y `.../start/with-version.json` (`{"cmd": "start", "v": 1}`)
- [ ] T036 [P] [US2] Crear ejemplos inválidos: `contract/examples/invalid/commands/set_rate/hz-too-high.json` (`hz: 150` → `maximum` en `/hz`, escenario US2-6), `.../set_rate/hz-not-integer.json` (`hz: 20.5` → `type` en `/hz`), `.../set_config/empty.json` (`{"cmd": "set_config"}` → `anyOf` en `""`), `.../set_config/negative-kp.json` (`minimum` en `/params/kp`), `.../start/wrong-version.json` (`v: 2` → `const` en `/v`) y `.../start/unknown-cmd.json` (`cmd: "go"` → `unknown_cmd` en `/cmd`)
- [ ] T037 [P] [US2] Crear ejemplos de la secuencia de corrida de los escenarios US2: `contract/examples/valid/event/run-finished-config-changed.json` (`summary.config.params.kp: 0.045` y `config_changed: true`, escenario US2-7), `contract/examples/valid/config/after-set-rate.json` (`rate_hz: 20`, escenario US2-5) y `contract/examples/valid/error/out-of-range-set-rate.json` (`code: "out_of_range"`, `cmd: "set_rate"`, escenario US2-6)
- [ ] T038 [US2] Completar § Comandos de `contract/contract-v1.md` (los 5 comandos generales): tabla `cmd` / campos / efecto / robot real (FR-029), reglas `start` con corrida activa → `run_active` y `stop` sin corrida → `no_run` (FR-031), `set_config` en corrida aplica al instante y marca `config_changed` (FR-034), comando rechazado sin efecto (FR-028), `run_id` único por sesión (FR-033), diagrama de estados de la corrida de data-model.md

**Checkpoint**: US1 y US2 funcionan; el optimizador tiene definido su ciclo `set_config` → `start` → `run_finished`.

---

## Phase 5: User Story 3 - Cargar pistas y ajustar el perfil del robot en el simulador (Priority: P3)

**Goal**: schemas de perfil, pista y comandos solo-sim; semántica de pista y perfil efectivo.

**Independent Test**: `uv run pytest tests/contract -k "examples and (track or robot-profile or reset or load or set_profile or load_track)" tests/unit/test_track_rules.py tests/unit/test_effective_profile.py` pasa (escenarios US3-1 a US3-3).

### Schemas

- [ ] T039 [P] [US3] Crear `contract/schemas/robot-profile.schema.json`: `$defs.profile_param(tipo)` como objeto `{default, measured, source}` con los tres obligatorios, `measured` del mismo tipo que `default` o `null` y `source` `{"enum": ["defined", "datasheet", "estimated", "current_robot"]}`; propiedades obligatorias según FR-036, cada una con su tipo y rango en `default` y `measured`: `id`, `firmware`, `hw_rev` (string; en `id`, `measured` `{"const": null}`); `line_sensors` (entero ≥ 1); `adc_bits` (entero 8…16); `sensor_pitch_m`, `sensor_offset_m`, `wheelbase_m`, `max_speed_mps`, `max_lateral_accel_mps2`, `battery_nominal_v` (número `exclusiveMinimum: 0`); `adc_white`, `adc_black` (entero 0…65535); `adc_noise` (entero ≥ 0); `motors` (`{"const": 2}`, fijo en v1); `battery_cells` (entero ≥ 1); `motor_tau_ms`, `control_period_ms` (número `exclusiveMinimum: 0`); `turbine`, `encoders`, `imu`, `battery_voltage_sense`, `lap_timing` (booleano); `turbine_suction_n` (número ≥ 0 o `null`); `encoder_ticks_per_rev` (entero ≥ 1 o `null`) (FR-035 a FR-037)
- [ ] T040 [P] [US3] Crear `contract/schemas/track.schema.json`: obligatorios `id` (string `minLength: 1`), `v` (`{"const": 1}`), `name` (string), `units` (`{"const": "m"}`), `board` (objeto con `width`, `height` número `exclusiveMinimum: 0`, ambos obligatorios), `line_width` (número `exclusiveMinimum: 0`), `closed` (booleano), `centerline` (array `minItems: 2` de pares `[x, y]`: array de 2 números, `minItems: 2`, `maxItems: 2`), `gaps` (array de objetos `{at: número ≥ 0, length: número > 0}`, ambos obligatorios), `start` (objeto con `at` número ≥ 0, obligatorio) y `rules_profile` (string `minLength: 1`); opcional `marks` sin restricción (FR-038, FR-040)
- [ ] T041 [P] [US3] Crear `contract/schemas/commands/reset.schema.json` (solo `cmd` `{"const": "reset"}`), `load.schema.json` (`robot_id` string `minLength: 1` obligatorio), `set_profile.schema.json` (`measured` obligatorio: objeto `minProperties: 1` cuyas claves están limitadas con `propertyNames` `{"enum": ["sensor_pitch_m", "sensor_offset_m", "adc_white", "adc_black", "adc_noise", "max_speed_mps", "motor_tau_ms", "wheelbase_m", "max_lateral_accel_mps2", "turbine_suction_n", "encoder_ticks_per_rev", "control_period_ms"]}` —solo parámetros físicos y de calibración; los 13 parámetros de `hello` quedan fuera—, y cuyos valores son número o `null`, con `encoder_ticks_per_rev` entero ≥ 1 o `null` y el resto con el rango de su parámetro en T039) y `load_track.schema.json` (`track` obligatorio con `$ref` a `../track.schema.json`); todos con `allOf` a `common#/$defs/command_envelope` (FR-029, FR-037)

### Semántica de pista y perfil efectivo

- [ ] T042 [US3] Crear `src/velocista_sim/contract/track_rules.py` con `track_violations(track: dict) -> list[Violation]` (data-model.md capa 3), solo si la pista pasó el schema: longitud = suma de distancias entre puntos consecutivos de `centerline`, más el tramo último→primero si `closed = true`; `track_at_range` en `/start/at` o `/gaps/<i>/at` si `at` está fuera de `[0, longitud]`; `track_point_outside_board` en `/centerline/<i>` si el punto está fuera de `[0, width] × [0, height]`; `track_gaps_overlap` en `/gaps/<j>` si el intervalo `[at, at + length)` del gap `j` se superpone con el de algún gap anterior; `track_sampling` en `/centerline/<i>` si la distancia al punto anterior está fuera de `0,005 m ± 10 %` (sin contar el tramo de cierre); conectarlo al gancho `_track_violations` de `src/velocista_sim/contract/validate.py` y aplicarlo también en `validate_command` para `load_track`, con los paths prefijados por `/track`
- [ ] T043 [P] [US3] Crear `tests/unit/test_track_rules.py`: pista recta abierta válida de 1 m (201 puntos cada 5 mm), pista cerrada cuadrada válida, y un caso por cada una de las 4 reglas de T042
- [ ] T044 [US3] Agregar a `src/velocista_sim/contract/validate.py` `effective_profile(profile: dict) -> dict[str, object]`, que devuelve para cada parámetro `measured` si no es `null` y si no `default` (FR-035), y exportarla en `src/velocista_sim/contract/__init__.py`
- [ ] T045 [P] [US3] Crear `tests/unit/test_effective_profile.py`: con `wheelbase_m = {"default": 0.130, "measured": null, …}` devuelve 0.130; con `measured: 0.128` devuelve 0.128 (escenario US3-3)

### Ejemplos

- [ ] T046 [P] [US3] Crear `contract/examples/valid/robot-profile/velocista-01-default.json` con todos los parámetros de FR-036 y sus valores por defecto v1 (`wheelbase_m` `{"default": 0.130, "measured": null, "source": "estimated"}`, etc.), y `contract/examples/valid/robot-profile/with-measured.json` con `wheelbase_m.measured: 0.128`
- [ ] T047 [P] [US3] Generar una pista válida pequeña y escribirla en `contract/examples/valid/track/oval-small.json` (cerrada, dentro de un `board` de 3,00 × 2,50 m, puntos cada 5 mm, un gap y `start`), con un script de una sola vez en el scratchpad (no se versiona el script), y `contract/examples/valid/track/straight-open.json` (recta abierta)
- [ ] T048 [P] [US3] Crear inválidos de pista en `contract/examples/invalid/track/`: `centerline-too-short.json` (1 punto → `minItems` en `/centerline`, escenario US3-2), `wrong-units.json` (`units: "cm"` → `const` en `/units`), `start-beyond-length.json` (`track_at_range` en `/start/at`), `point-outside-board.json` (recta abierta cuyo primer punto es `[-0.005, 0.5]` y el resto dentro del tablero, a 5 mm entre sí → `track_point_outside_board` en `/centerline/0`), `gaps-overlap.json` (`track_gaps_overlap` en `/gaps/1`) y `bad-sampling.json` (recta abierta cada 5 mm a la que se le quita el punto de índice 10, de modo que el nuevo punto 10 queda a 10 mm del 9 → `track_sampling` en `/centerline/10`)
- [ ] T049 [P] [US3] Crear inválidos de perfil en `contract/examples/invalid/robot-profile/`: `missing-measured.json` (`required` en `/wheelbase_m/measured`), `bad-source.json` (`enum` en `/wheelbase_m/source`), `id-measured.json` (`id.measured: "x"` → `const` en `/id/measured`)
- [ ] T050 [P] [US3] Crear ejemplos de comandos solo-sim: válidos `contract/examples/valid/commands/reset/pdf-reset.json`, `.../load/pdf-load.json`, `.../set_profile/pdf-set-profile.json` (`measured: {"wheelbase_m": 0.128}`), `.../load_track/oval-small.json` (envolviendo la pista de T047); inválidos `contract/examples/invalid/commands/load/missing-robot-id.json` (`required` en `/robot_id`), `.../set_profile/unknown-param.json` (clave `wheelbase` → `enum` en `/measured`: jsonschema informa `propertyNames` como el `enum` interno, en el path del objeto), `.../set_profile/change-id.json` (clave `id` → `enum` en `/measured`), `.../set_profile/change-line-sensors.json` (`{"line_sensors": 8}` → `enum` en `/measured`, escenario US3-5) y `.../load_track/invalid-track.json` (pista con `units: "cm"` → `const` en `/track/units`); y el mensaje con que el servidor rechaza un parámetro de `hello`: válido `contract/examples/valid/error/set-profile-hello-param.json` (`code: "invalid_params"`, `cmd: "set_profile"`)
- [ ] T051 [US3] Completar en `contract/contract-v1.md` § Comandos (los 4 solo-sim, marcados como tales; error `run_active` en corrida, FR-032; `load` reenvía `hello` y luego `config` y es el único que cambia datos de `hello`, FR-013; `set_profile` solo acepta parámetros físicos y de calibración, rechaza los de `hello` con `invalid_params` y se aplica todo o nada, FR-037), § Perfil del robot (forma `{default, measured, source}` con `source` ∈ `defined`/`datasheet`/`estimated`/`current_robot`, tabla de FR-036 con la columna "Campo en `hello`", valor efectivo) y § Pista track v1 (campos de FR-038, origen de coordenadas en la esquina inferior izquierda con x a la derecha e y hacia arriba, tolerancia de muestreo ±10 %, reglas de FR-039, `marks` reservado FR-040, la geometría nunca sale hacia los clientes FR-021)

**Checkpoint**: US1–US3 completas; el trazador tiene un formato de exportación verificable.

---

## Phase 6: User Story 4 - Implementar el contrato en el robot real (ESP32) (Priority: P4)

**Goal**: reglas contextuales que dependen de las capacidades y de `source`, y ejemplos del robot real.

**Independent Test**: `uv run pytest tests/contract -k "examples and (telemetry or catalog or config or event or hello)" tests/unit/test_context_rules.py` pasa; escenarios US4-1 a US4-6.

- [ ] T052 [US4] Agregar a `src/velocista_sim/contract/context_rules.py` las reglas restantes de data-model.md capa 2: `odometry_without_capability` (en `/odometry`, si existe con `encoders = imu = false`), `odometry_encoder_fields` (en `/odometry/distance_m` o `/odometry/speed_mps`, si existen sin `encoders`), `odometry_imu_fields` (en `/odometry/heading_rad`, sin `imu`), `battery_without_sense` (en `/battery_v`, con `voltage_sense = false`), `sim_truth_without_sim` (en `/sim_truth`, con `source = "robot"`), `lap_without_timing` (en `/lap` de `telemetry`, o en `/event` de un `event` con `event = "lap"`, con `lap_timing = false`), `summary_laps_without_timing` (en `/summary/laps`, `/summary/best_lap_ms` o `/summary/avg_lap_ms`, si no son `null` con `lap_timing = false`), `summary_laps_missing` (en `/summary/laps` de un `run_finished`, si `laps` es `null` con `lap_timing = true`; `best_lap_ms` y `avg_lap_ms` siguen la regla de schema de `laps ≥ 1`), `catalog_robot_real` (en `/robots` o `/tracks`, con `source = "robot"` si `robots ≠ [robot.id]` o `tracks ≠ []`) y `track_id_robot_real` (en `/track_id` de `config`, con `source = "robot"` y valor no nulo); y las reglas de presencia obligatoria en `telemetry` (A1): `odometry_missing` (en `/odometry`, si falta con `encoders` o `imu`), `odometry_encoder_fields_missing` (en `/odometry/distance_m` y/o `/odometry/speed_mps`, si falta alguno con `encoders = true` y `odometry` presente), `odometry_imu_fields_missing` (en `/odometry/heading_rad`, si falta con `imu = true` y `odometry` presente), `battery_v_missing` (en `/battery_v`, si falta con `voltage_sense = true`), `sim_truth_missing` (en `/sim_truth`, si falta con `source = "sim"`) y `lap_missing` (en `/lap`, si falta con `running = true` y `lap_timing = true`); cuando `odometry_without_capability` u `odometry_missing` se cumplen, no informar además las reglas por campo de `odometry`
- [ ] T053 [P] [US4] Crear `contract/examples/valid/hello/with-encoders-imu.json` y `contract/examples/valid/hello/encoders-only.json`, ambos copiados de `robot-real.json` (`source: "robot"`, `voltage_sense: false`, `lap_timing: false`) y con `encoders: true`, `imu: true` en el primero y `encoders: true`, `imu: false` en el segundo, para que sus telemetrías no necesiten `sim_truth`, `battery_v` ni `lap`; y `contract/examples/valid/hello/imu-only.json`, igual pero con `encoders: false`, `imu: true`
- [ ] T054 [P] [US4] Crear ejemplos válidos del robot real: `contract/examples/valid/telemetry/robot-real.json` (`hello: "robot-real"`, sin `sim_truth`, `battery_v` ni `lap`), `contract/examples/valid/telemetry/with-odometry.json` (`hello: "with-encoders-imu"`, `odometry` del PDF §8 con sus tres campos), `contract/examples/valid/telemetry/encoders-odometry.json` (`hello: "encoders-only"`, solo `distance_m` y `speed_mps`, escenario US4-3), `contract/examples/valid/event/robot-real-run-finished.json` (`laps`, `best_lap_ms`, `avg_lap_ms` en `null`, escenario US4-5), `contract/examples/valid/catalog/robot-real.json` (`robots: ["velocista-01"]`, `tracks: []`, escenario US4-4) y `contract/examples/valid/config/robot-real.json` (`track_id: null`)
- [ ] T055 [P] [US4] Crear ejemplos inválidos de capacidades, cada uno partiendo de un `telemetry` válido para su `hello` (con todos los campos que ese `hello` hace obligatorios) para que solo falle la regla indicada: en `contract/examples/invalid/telemetry/`: `sim-truth-robot.json` (`hello: "robot-real"` → `sim_truth_without_sim` en `/sim_truth`, US4-1), `odometry-without-capability.json` (`hello: "sim-default"` → `odometry_without_capability` en `/odometry`, US4-2), `odometry-heading-without-imu.json` (`hello: "encoders-only"` → `odometry_imu_fields` en `/odometry/heading_rad`), `battery-without-sense.json` (`hello: "robot-real"` → `battery_without_sense` en `/battery_v`) y `lap-without-timing.json` (`hello: "robot-real"` → `lap_without_timing` en `/lap`, US4-5); en `contract/examples/invalid/event/`: `lap-event-without-timing.json` (`lap_without_timing` en `/event`) `run-finished-laps-without-timing.json` (`summary_laps_without_timing` en `/summary/laps`, `/summary/best_lap_ms` y `/summary/avg_lap_ms`) y `run-finished-laps-null-with-timing.json` (`hello: "sim-default"`, `laps`, `best_lap_ms` y `avg_lap_ms` en `null` → `summary_laps_missing` en `/summary/laps`); en `contract/examples/invalid/catalog/robot-real-with-tracks.json` (`catalog_robot_real` en `/tracks`) y `contract/examples/invalid/config/robot-real-with-track.json` (`track_id_robot_real` en `/track_id`); y los de presencia obligatoria en `contract/examples/invalid/telemetry/`: `odometry-missing.json` (`hello: "encoders-only"`, sin `odometry` → `odometry_missing` en `/odometry`, escenario US4-6), `odometry-speed-missing.json` (`hello: "encoders-only"`, `odometry` solo con `distance_m` → `odometry_encoder_fields_missing` en `/odometry/speed_mps`), `odometry-heading-missing.json` (`hello: "with-encoders-imu"`, sin `heading_rad` → `odometry_imu_fields_missing` en `/odometry/heading_rad`), `odometry-distance-without-encoders.json` (`hello: "imu-only"`, `odometry` con `heading_rad` y `distance_m` → `odometry_encoder_fields` en `/odometry/distance_m`), `battery-v-missing.json`, `sim-truth-missing.json` y `lap-missing.json` (los tres con `hello: "sim-default"`, el telemetry del PDF sin `battery_v`, sin `sim_truth` y sin `lap` respectivamente → `battery_v_missing` en `/battery_v`, `sim_truth_missing` en `/sim_truth`, `lap_missing` en `/lap`)
- [ ] T056 [P] [US4] Ampliar `tests/unit/test_context_rules.py` con un caso por cada regla de T052 (incluidas las 6 `*_missing` de `telemetry` y `summary_laps_missing`), que `odometry_without_capability` y `odometry_missing` no se acompañan de las reglas por campo, que un `telemetry` con `running = false` y `lap_timing = true` no exige `lap`, y que el mismo `telemetry` es válido o inválido según el `hello` que se pase (simula el cambio de `hello` tras `load`)
- [ ] T057 [US4] Completar en `contract/contract-v1.md` una § Paridad simulador–robot real: tabla de campos condicionados (`odometry` y cada uno de sus campos, `battery_v`, `sim_truth`, `lap`, `summary.laps…`) con la condición que los hace obligatorios y la que los prohíbe ("presente si y solo si", FR-018), motores fijos en 2 en v1, comportamiento del robot real ante comandos solo-sim (`sim_only`), `list`, `track_id: null` y desconexión (detener motores, FR-007), y la regla de que los clientes funcionan sin `lap` (FR-024a)

**Checkpoint**: las cuatro historias están completas e independientes.

---

## Phase 7: Polish & cross-cutting

**Purpose**: verificaciones globales (SC-001, SC-005), documentación y cierre.

- [ ] T058 Crear `tests/contract/test_coverage.py`: (a) SC-001: existe al menos un ejemplo en `valid/` y uno en `invalid/` para cada schema de `messages/` y `commands/` (las 9 carpetas `commands/<cmd>/` y las 6 de mensajes), para `robot-profile` y para `track`, y cada uno de los 4 subtipos de `event` aparece en algún ejemplo válido; (b) SC-005: cada identificador de regla de las capas 2 y 3 de data-model.md aparece en al menos un `expected`; (c) SC-003: hay al menos un ejemplo con `description` que empieza por `"PDF v1.1:"` para cada mensaje y comando que el PDF ejemplifica; (d) FR-002 (G1): para cada schema que tiene campos obligatorios además del discriminador, hay al menos un ejemplo inválido con `rule = "required"` y otro con `rule = "type"`, y para cada schema que declara cotas numéricas (`minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`) hay al menos un inválido con una de esas reglas; los schemas sin campos propios (`start`, `stop`, `list`, `reset`) quedan exentos; completar los ejemplos que falten si el test lo detecta
- [ ] T059 [P] Revisar `contract/contract-v1.md` contra la spec: cada FR-005 a FR-040 tiene su lugar en el texto, sin `TODO` ni secciones vacías; enlaces a schemas y ejemplos correctos
- [ ] T060 [P] Agregar a `README.md` una sección breve en español: qué es el contrato, dónde están `contract/contract-v1.md`, los schemas y los ejemplos, y cómo validar (`uv run pytest`, uso de `validate_message`), con enlace a `specs/001-contrato-v1/quickstart.md`
- [ ] T061 Enmendar `.specify/memory/constitution.md` a **v1.1.1** (PATCH): quitar de *Pendientes* el ítem de JSON Schemas (o la sección si queda vacía), actualizar la línea de versión y `Last Amended`, en un commit `docs(constitution): …`
- [ ] T062 Ejecutar todos los pasos de `specs/001-contrato-v1/quickstart.md` (`uv sync --locked`, `uv run pytest`, el filtro `-k examples` y la validación a mano del paso 3) y corregir lo que falle; verificar que `git status` no muestra archivos sin versionar inesperados
- [ ] T063 Organizar la revisión del contrato (SC-004, SC-006): un integrante de front, uno de backend y uno de firmware leen `contract/contract-v1.md` con sus schemas y ejemplos, intentando responder solo con el contrato las preguntas de su cliente (conexión, corrida completa, resumen; qué emitir con el robot real). Registrar el resultado en `specs/001-contrato-v1/review.md`: fecha, revisores por rol, preguntas que el contrato no respondió, cambios acordados y veredicto (aprobado / aprobado con cambios). Los cambios que surjan se aplican al contrato, a los schemas y a los ejemplos antes de integrar en `main`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (fase 1)**: sin dependencias.
- **Foundational (fase 2)**: depende de Setup; **bloquea** todas las historias. T008 depende de T006 y T007; T009 de T008; T012 de T010.
- **US1–US4 (fases 3–6)**: dependen solo de Foundational.
- **Polish (fase 7)**: depende de las cuatro historias (T058 exige ejemplos de todo). T063 (revisión por front, backend y firmware) va al final, con el contrato completo.

### User Story Dependencies

- **US1 (P1)**: solo Foundational.
- **US2 (P2)**: solo Foundational. T037 agrega ejemplos de mensajes que se validan con los schemas de US1 (T015, T017, T019); si US2 se hace antes que US1, T037 espera a esos schemas.
- **US3 (P3)**: solo Foundational. T050 (`load_track/oval-small.json`) usa la pista de T047.
- **US4 (P4)**: necesita `context_rules.py` (T028 de US1) y los schemas de mensajes de US1; se hace después de US1.
- Tareas que editan el mismo archivo y por eso son secuenciales: `contract/contract-v1.md` (T013 → T031 → T038 → T051 → T057 → T059), `validate.py` (T008 → T028 → T042 → T044), `context_rules.py` (T028 → T052), `test_context_rules.py` (T030 → T056).

### Within Each User Story

- Schemas → ejemplos válidos → ejemplos inválidos → reglas propias → texto del contrato.
- Los ejemplos inválidos se escriben sabiendo que deben fallar **solo** por sus `expected`: si `test_examples.py` reporta violaciones adicionales, se corrige el ejemplo, no el test.

### Parallel Opportunities

- Setup: T003 y T004.
- Foundational: T006, T007, T010, T011, T013 en paralelo; luego T008 → T009 y T012.
- US1: los 6 schemas (T014–T019) en paralelo; luego todos los ejemplos (T020–T027) en paralelo; T029 y T030 en paralelo tras T028.
- US2: T032–T037 en paralelo.
- US3: T039–T041 en paralelo; T043, T045–T050 en paralelo cuando estén sus prerrequisitos.
- US1, US2 y US3 pueden avanzar en paralelo entre sí tras Foundational (con las salvedades indicadas).

---

## Parallel Example: User Story 1

```text
# Los seis schemas de mensajes a la vez:
Task: "T014 hello.schema.json en contract/schemas/messages/"
Task: "T015 config.schema.json en contract/schemas/messages/"
Task: "T016 telemetry.schema.json en contract/schemas/messages/"
Task: "T017 event.schema.json en contract/schemas/messages/"
Task: "T018 catalog.schema.json en contract/schemas/messages/"
Task: "T019 error.schema.json en contract/schemas/messages/"

# Después, todos los ejemplos a la vez:
Task: "T020–T024 ejemplos válidos en contract/examples/valid/"
Task: "T025–T027 ejemplos inválidos en contract/examples/invalid/"
```

---

## Implementation Strategy

### MVP primero (solo US1)

1. Fase 1 (Setup) y fase 2 (Foundational).
2. Fase 3 (US1): mensajes servidor→cliente con sus ejemplos y las reglas de sensores.
3. **Parar y validar**: `uv run pytest` en verde y CI en verde. El front, el backend y el optimizador ya pueden desarrollar contra los mensajes salientes.

### Entrega incremental

1. Setup + Foundational → base lista.
2. US1 → los clientes ya pueden interpretar todo lo que reciben (MVP).
3. US2 → los clientes ya pueden controlar corridas y el optimizador ya tiene su ciclo.
4. US3 → el trazador ya puede exportar pistas y el simulador recibir perfiles medidos.
5. US4 → el firmware ya tiene definido qué emitir y qué no.
6. Polish → cobertura SC-001/SC-005, README y enmienda PATCH de la constitución.

Commit al terminar cada tarea o grupo lógico, con Conventional Commits.

---

## Notes

- [P] = archivos distintos y sin dependencias pendientes.
- Las reglas de secuencia de sesión (FR-008, FR-010, orden de `seq`, FR-025) quedan **fuera** de esta feature (research R8); no hay tareas para ellas.
- El script que genera la pista de ejemplo (T047) no se versiona; solo se versiona el JSON resultante.
- Si al escribir un ejemplo inválido jsonschema reporta una palabra clave distinta de la prevista en la tarea (p. ej. por `if`/`then` o `propertyNames`), se registra en `expected` la que realmente reporta, siempre que el motivo sea el que el ejemplo pretende ilustrar.
