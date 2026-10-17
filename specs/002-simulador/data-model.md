# Data Model: Simulador de velocista

Entidades internas del simulador. Los mensajes externos están definidos en
`contract/contract-v1.md` y no se repiten aquí. Decisiones y valores numéricos: ver
[research.md](./research.md).

## Visión general

```text
                        ┌──────────────────────── server ────────────────────────┐
 WebSocket /ws ◄──────► │ app ── Pacer (asyncio, reloj) ── Session (sin E/S)     │
                        │                                   │      │             │
                        │                     sensors list[int]   (left, right)  │
                        └───────────────────────────────────┼──────┼─────────────┘
                                                            ▼      ▲
                                world (pista, física, ruido)   robot (línea, PID)
                                   └── truth → sim_truth          (no se importan entre sí)
```

## Settings (`server.settings`)

| Campo | Tipo | Origen | Defecto |
|---|---|---|---|
| `port` | int | `PORT` | 8000 |
| `seed` | int | `VELOCISTA_SEED` | 1 |
| `config_dir` | Path | `VELOCISTA_CONFIG_DIR` | `config/` del repo (se busca subiendo desde el módulo) |
| `max_sessions` | int ≥ 1 | `VELOCISTA_MAX_SESSIONS` | 20 |
| `default_robot` | str | constante | `velocista-01` |
| `default_track` | str | constante | `oval-01` |

## Catalog (`server.catalog`)

Se carga una vez al arrancar; inmutable y compartido (solo lectura) entre sesiones.

| Campo | Tipo | Notas |
|---|---|---|
| `profiles` | `dict[str, dict]` | perfil robot-profile por `id`; validado con `validate_profile` |
| `tracks` | `dict[str, dict]` | pista track v1 por `id`; validada con `validate_track` |

Validación al arrancar (falla el arranque si no se cumple): nombre de archivo = `id`;
`default_robot` y `default_track` presentes; perfiles con `motors = 2` y `encoders`, `imu`,
`turbine` efectivos en `false`.

## ControllerConfig

| Campo | Tipo | Regla |
|---|---|---|
| `controller` | `"pid"` | fijo en v1 |
| `kp`, `ki`, `kd` | float ≥ 0 | defecto 0,045 · 0 · 0,9 |
| `base_speed` | int 0–255 | defecto 180 |

Inmutable (dataclass `frozen`); `set_config` produce una nueva combinando los campos enviados
(incluidos los parámetros sueltos dentro de `params`). Se serializa con la forma
`{controller, params:{kp,ki,kd}, base_speed}` para `config` y para `summary.config`.

## Session (`server.session`)

Una por conexión. Núcleo síncrono: no lee el reloj ni hace E/S.

| Campo | Tipo | Notas |
|---|---|---|
| `session_id` | str | `"s-" + 8 hex` (uuid4); único; lo único no reproducible |
| `step_index` | int | pasos ejecutados; `t_ms = step_index · 2` |
| `seq` | int | próximo `seq` de telemetría; empieza en 0, nunca se reinicia |
| `profile` | dict | perfil vigente (con `measured` propios de la sesión) |
| `effective` | dict | `effective_profile(profile)` en caché |
| `hello` | dict | último `hello` emitido (contexto de validación en tests) |
| `track` | dict | pista vigente (track v1) |
| `session_tracks` | dict[str, dict] | pistas cargadas con `load_track` en esta sesión |
| `config` | ControllerConfig | vigente |
| `rate_hz` | int 10–100 | defecto 50 |
| `rate_anchor_ms`, `rate_tick` | int | calendario de telemetría (research R5) |
| `seed` | int | semilla base (`VELOCISTA_SEED`) |
| `rng` | `numpy.random.Generator` | generador vigente: `PCG64(SeedSequence([seed, 0]))` fuera de corrida; `PCG64(SeedSequence([seed, n]))` nuevo en cada `start` de la corrida `n` (research R6) |
| `world` | World | mundo propio |
| `robot` | Robot | robot propio |
| `run` | Run \| None | como máximo una corrida activa |
| `run_counter` | int | número de la última corrida: da el `run_id` `"r-<n>"` y la semilla de la corrida `[seed, n]` |
| `inbox` | deque[str] | frames recibidos, aplicados al inicio del próximo paso |

### Orden de un paso (`Session.step()`)

1. Aplicar **todos** los comandos del `inbox` en orden de llegada (FR-032); cada uno puede
   emitir `config`, `hello`, `catalog`, `error` o eventos (`run_started`, `run_finished`).
2. Si toca tick de control: `sensors = world.read_sensors(rng)` →
   `out = robot.tick(sensors, running)` → `world.set_motor_pwm(out.left, out.right)`
   (sin corrida, `robot.tick` devuelve motores 0 y `control` en 0).
3. `world.step()` (física, `dt = 2 ms`) y `step_index += 1`.
4. Con corrida activa: `world.detect()` → vueltas completadas (→ `event lap`) y salida de pista
   (→ `event off_track` + `event run_finished`, la corrida termina).
5. Si toca tick de telemetría: emitir `telemetry` con `seq` y luego `seq += 1`.

Todos los mensajes de un paso llevan el `t_ms` posterior al paso 3, salvo las respuestas a
comandos (paso 1), que llevan el `t_ms` del inicio del paso; así `t_ms` nunca decrece.

### Reglas de comandos (resumen; detalle en [contracts/ws-session.md](./contracts/ws-session.md))

| Comando | Con corrida | Sin corrida | Respuesta |
|---|---|---|---|
| `start` | `run_active` | crea Run `n`, reinicia mundo/robot, `rng` de `[seed, n]` | `event run_started` |
| `stop` | termina Run | `no_run` | `event run_finished` |
| `set_config` | aplica; `run.config_changed = true` | aplica | `config` |
| `set_rate` | aplica | aplica | `config` |
| `list` | responde | responde | `catalog` |
| `reset` | `run_active` | robot a la salida, detenido | — (sin mensaje) |
| `load` | `run_active` | perfil nuevo, robot a la salida | `hello` + `config` |
| `set_profile` | `run_active` | `measured` todo o nada | `config` |
| `load_track` | `run_active` | pista nueva, robot a la salida | `config` |

## Run

| Campo | Tipo | Notas |
|---|---|---|
| `run_id` | str | `"r-<n>"`, único en la sesión |
| `number` | int | `n` ≥ 1; con la semilla base determina el ruido de la corrida |
| `start_config` | ControllerConfig | para `summary.config` |
| `config_changed` | bool | `true` si se aceptó `set_config` durante la corrida |
| `track_id` | str | pista de la corrida |
| `lap_times_ms` | list[int] | > 0 cada uno |
| `lap_start_ms` | int | `t_ms` de inicio de la vuelta en curso |
| `off_tracks` | int | 0 o 1 en v1 (la salida termina la corrida) |

Derivados: `laps = len(lap_times_ms)` (o `null` si `lap_timing = false`), `best_lap_ms = min`,
`avg_lap_ms = round(mean)` (`null` sin vueltas), `lap.current_ms = t_ms − lap_start_ms`.

### Estados

```text
inactiva ──start──► activa ──stop────────────────► run_finished ──► inactiva
                      │ ──off_track (mundo)──► off_track ► run_finished ──► inactiva
                      │ ──set_config──► activa (config_changed = true)
                      └ ──desconexión──► sesión descartada (sin run_finished)
```

## TrackGeometry (`world.track`)

Precalculada al cargar una pista; inmutable.

| Campo | Tipo | Notas |
|---|---|---|
| `points` | ndarray (P, 2) | `centerline` |
| `cum_s` | ndarray (P,) | longitud acumulada por punto |
| `length` | float | incluye el tramo de cierre si `closed` |
| `closed` | bool | |
| `ink_a`, `ink_b` | ndarray (M, 2) | extremos de los tramos con tinta (centerline menos `gaps`) |
| `grid` | dict[(i, j), ndarray] | celdas de 0,05 m → índices de tramos con tinta |
| `board` | (w, h) | tablero |
| `line_width` | float | |
| `start_s` | float | `start.at` |

Operaciones: `pose_at(s) -> (x, y, heading)`; `project(x, y, hint) -> (s, index)`;
`ink_candidates(bbox) -> índices`.

## WorldParams / RobotParams

Construidos por la sesión a partir del perfil efectivo; cada paquete recibe solo lo suyo.

| WorldParams | RobotParams |
|---|---|
| `line_sensors`, `sensor_pitch_m`, `sensor_offset_m` | `line_sensors` |
| `adc_bits`, `adc_white`, `adc_black`, `adc_noise` | `adc_white`, `adc_black` (calibración propia) |
| `max_speed_mps`, `motor_tau_ms`, `wheelbase_m`, `max_lateral_accel_mps2` | `control_period_ms` |
| `battery_nominal_v` | — |

## World (`world.world`)

| Estado | Tipo | Notas |
|---|---|---|
| `x`, `y`, `theta` | float | pose verdadera (m, rad) |
| `v_left`, `v_right` | float | velocidad real de cada rueda (m/s) |
| `pwm_left`, `pwm_right` | int | último PWM aplicado |
| `distance_m` | float | recorrido del eje, ≥ 0 |
| `progress_s`, `proj_index` | float, int | avance desenvuelto desde la salida y pista para la proyección |
| `laps_done` | int | vueltas completadas en la corrida |
| `lost_distance_m`, `lost_time_ms` | float, int | sin ver tinta (detección de salida) |

Operaciones: `reset_to_start()`, `set_motor_pwm(l, r)`, `read_sensors(rng) -> list[int]`,
`step()`, `detect(t_ms) -> list[WorldEvent]` (`LapCompleted`, `OffTrack`),
`truth() -> {x, y, theta, speed_mps, distance_m}`, `battery_v() -> float`.

## Robot (`robot.robot`)

| Estado | Tipo | Notas |
|---|---|---|
| `config` | ControllerConfig-like | `kp, ki, kd, base_speed` (sin importar `server`) |
| `last_position` | int | última `line_position` con línea vista |
| `integral` | float | Σ e |
| `prev_error` | int \| None | `None` tras reinicio (sin patada derivativa) |
| `last_output` | ControlOutput | lo que informa la telemetría |

`ControlOutput`: `line_position`, `line_lost`, `error`, `p`, `i`, `d`, `out`,
`left`, `right`. Operaciones: `reset()`, `set_config(...)`, `tick(sensors, running) -> ControlOutput`.

## Reglas de validación (resumen)

| Regla | Dónde | Origen |
|---|---|---|
| Comando válido según su schema; código por tipo de violación | `server.commands` | research R8 |
| Pista de `load_track` válida (schema + reglas track) | `validate_command` | contrato |
| `set_profile` todo o nada | `Session` aplica solo si la validación pasa entera | FR-034 |
| `line_position` 0 … (N−1)·1000; `error = line_position − (N−1)·500` | `robot.line` | FR-018 |
| `sensors` en 0 … 2^`adc_bits` − 1, longitud N | `world.sensors` | FR-012 |
| PWM −255 … 255 | `robot.robot` | FR-019 |
| Ningún mensaje con geometría de pista | helper de tests | FR-008 |
