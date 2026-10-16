# Fase 1 — Modelo de datos: Contrato v1

**Feature**: [spec.md](./spec.md) · **Decisiones**: [research.md](./research.md)

Los campos, tipos, unidades y rangos de cada mensaje están en las tablas de la spec (FR-013 a
FR-040) y no se repiten aquí. Este documento fija cómo se reparten en archivos de schema, qué
reglas verifica cada capa y cómo evolucionan la sesión y la corrida.

## Entidades y archivos

| Entidad (spec) | Discriminador | Schema en `contract/schemas/` | Requisitos |
|---|---|---|---|
| Piezas comunes | — | `common.schema.json` (`$defs`) | FR-010, FR-012 |
| `hello` | `type` | `messages/hello.schema.json` | FR-013, FR-014 |
| `config` | `type` | `messages/config.schema.json` | FR-015, FR-016 |
| `telemetry` | `type` | `messages/telemetry.schema.json` | FR-017 a FR-021 |
| `event` (4 subtipos) | `type` + `event` | `messages/event.schema.json` | FR-022 a FR-025 |
| `catalog` | `type` | `messages/catalog.schema.json` | FR-026 |
| `error` | `type` | `messages/error.schema.json` | FR-027 |
| Comandos (9) | `cmd` | `commands/<cmd>.schema.json` | FR-011, FR-029 a FR-034, FR-037 |
| Perfil del robot | — | `robot-profile.schema.json` | FR-035 a FR-037 |
| Pista track v1 | — | `track.schema.json` | FR-038 a FR-040 |

`commands/load_track.schema.json` referencia `track.schema.json`; `commands/set_profile.schema.json`
referencia los nombres de parámetro de `robot-profile.schema.json`.

### `$defs` de `common.schema.json`

| `$def` | Contenido |
|---|---|
| `envelope` | `type` (string), `v` (`const: 1`), `t_ms` (entero ≥ 0); los tres obligatorios |
| `command_envelope` | `cmd` (string, obligatorio), `v` (`const: 1`, opcional) |
| `run_id` | string no vacío |
| `pwm` | entero −255…255 |
| `base_speed` | entero 0…255 |
| `rate_hz` | entero 10…100 |
| `pid_params` | `kp`, `ki`, `kd`: número ≥ 0, los tres obligatorios en `config` |
| `controller_config` | `controller` (`enum: ["pid"]`), `params` (`pid_params`), `base_speed` |
| `track_id` | string no vacío o `null` |
| `error_code` | `enum` con los 11 códigos de FR-027 |

### Perfil del robot

Objeto con un miembro por parámetro de la tabla FR-036. Cada miembro tiene la forma
`profile_param`: `{default, measured, source}`, con `measured` del mismo tipo que `default` o
`null`, y `source ∈ {defined, datasheet, estimated, current_robot}`. Los rangos de cada `default`
y `measured` se declaran por parámetro (p. ej. `wheelbase_m` > 0; `motors` fijo en 2). Valor
efectivo: `measured ?? default` (FR-035). `id` no admite `measured`.

Los parámetros se dividen en dos grupos (FR-036, FR-037):

- **Parámetros de `hello`** (13): `id`, `firmware`, `hw_rev`, `line_sensors`, `adc_bits`,
  `motors`, `turbine`, `encoders`, `imu`, `lap_timing`, `battery_cells`, `battery_nominal_v`,
  `battery_voltage_sense`. Solo cambian con `load`, que reenvía `hello` y `config`.
- **Parámetros físicos y de calibración** (12): `sensor_pitch_m`, `sensor_offset_m`,
  `adc_white`, `adc_black`, `adc_noise`, `max_speed_mps`, `motor_tau_ms`, `wheelbase_m`,
  `max_lateral_accel_mps2`, `turbine_suction_n`, `encoder_ticks_per_rev`, `control_period_ms`.
  Son los únicos que acepta `set_profile` (`propertyNames` en `commands/set_profile`).

## Reglas de validación

Cada regla tiene un identificador estable que usan los ejemplos inválidos en `expected[].rule`.
Las reglas de schema usan la palabra clave de JSON Schema que falla; las demás, el identificador
de esta tabla.

### Capa 1 — Schema (sin contexto)

Tipos, obligatorios, enums y rangos fijos de las tablas de la spec, más:

| Regla | Dónde | Expresión |
|---|---|---|
| `run_id` si y solo si `running` | `telemetry` | `if running=true then required run_id else not required run_id` |
| `lap` solo con corrida | `telemetry` | `if running=false then not required lap` |
| `set_config` no vacío | `commands/set_config` | `anyOf` de `required: [controller]`, `[params]`, `[base_speed]` |
| Subtipo de evento | `event` | `if event=lap then required lap, lap_ms`, etc. |
| `best_lap_ms`/`avg_lap_ms` | `event` (`run_finished`) | `if laps ∈ {0, null} then null else entero > 0` |
| `measured` en `id` | `robot-profile` | `measured: null` fijo |
| Motores en v1 | `hello`, `robot-profile` | `capabilities.motors` y `motors.default` `{"const": 2}` |
| `set_profile` solo físicos | `commands/set_profile` | `propertyNames` `enum` con los 12 parámetros físicos y de calibración |

### Capa 2 — Contextual (requiere `hello`)

| Regla (`rule`) | Mensaje | Condición de fallo | Requisito |
|---|---|---|---|
| `sensors_length` | `telemetry` | `len(sensors) ≠ capabilities.line_sensors` | FR-018 |
| `sensor_range` | `telemetry` | algún valor > `2^adc_bits − 1` | FR-018 |
| `line_position_range` | `telemetry` | `line_position > (line_sensors − 1) × 1000` | FR-018 |
| `error_consistency` | `telemetry` | `error ≠ line_position − (line_sensors − 1) × 500` | FR-018 |
| `odometry_without_capability` | `telemetry` | `odometry` presente con `encoders = imu = false` | FR-019 |
| `odometry_encoder_fields` | `telemetry` | `distance_m`/`speed_mps` presentes sin `encoders` | FR-019 |
| `odometry_imu_fields` | `telemetry` | `heading_rad` presente sin `imu` | FR-019 |
| `battery_without_sense` | `telemetry` | `battery_v` presente con `voltage_sense = false` | FR-018 |
| `sim_truth_without_sim` | `telemetry` | `sim_truth` presente con `source = "robot"` | FR-020 |
| `lap_without_timing` | `telemetry`, `event` | bloque `lap` o `event lap` con `lap_timing = false` | FR-024 |
| `summary_laps_without_timing` | `event` (`run_finished`) | `laps`, `best_lap_ms` o `avg_lap_ms` no nulos con `lap_timing = false` | FR-024 |
| `catalog_robot_real` | `catalog` | `source = "robot"` y `robots ≠ [robot.id]` o `tracks ≠ []` | FR-026 |
| `track_id_robot_real` | `config` | `source = "robot"` y `track_id ≠ null` | FR-015 |
| `odometry_missing` | `telemetry` | `odometry` ausente con `encoders` o `imu` | FR-018, FR-019 |
| `odometry_encoder_fields_missing` | `telemetry` | `distance_m` o `speed_mps` ausente con `encoders = true` (y `odometry` presente) | FR-019 |
| `odometry_imu_fields_missing` | `telemetry` | `heading_rad` ausente con `imu = true` (y `odometry` presente) | FR-019 |
| `battery_v_missing` | `telemetry` | `battery_v` ausente con `voltage_sense = true` | FR-018 |
| `sim_truth_missing` | `telemetry` | `sim_truth` ausente con `source = "sim"` | FR-020 |
| `lap_missing` | `telemetry` | bloque `lap` ausente con `running = true` y `lap_timing = true` | FR-018, FR-024 |

Las reglas `*_missing` informan el `path` del campo que falta (p. ej. `/battery_v`), con la misma
convención que `required`. Si falta `odometry` entera, solo se informa `odometry_missing`, no las
reglas por campo.

El contexto es siempre el **último** `hello` de la sesión: tras un `load` el servidor envía un
`hello` nuevo y los mensajes siguientes se validan con él (FR-013). Elegir qué `hello` pasar es
responsabilidad de quien llama al validador.

Si el mensaje no es `hello` y no se entrega `hello`, el validador aplica solo la capa 1 e informa
que las reglas contextuales no se evaluaron (no es un error).

### Capa 3 — Semántica de pista (sin contexto)

| Regla (`rule`) | Condición de fallo | Requisito |
|---|---|---|
| `track_at_range` | algún `gaps[].at` o `start.at` fuera de [0, longitud de `centerline`] | FR-039 |
| `track_point_outside_board` | algún punto fuera de `[0, width] × [0, height]` (origen en la esquina inferior izquierda, x a la derecha, y hacia arriba) | FR-038, FR-039 |
| `track_gaps_overlap` | dos `gaps` con intervalos `[at, at + length)` superpuestos | FR-039 |
| `track_sampling` | distancia entre puntos consecutivos fuera de 0,005 m ± 10 % (sin contar el tramo de cierre) | FR-038 |

La longitud de `centerline` es la suma de distancias entre puntos consecutivos (más el tramo de
cierre si `closed = true`).

### Fuera de esta feature — reglas de secuencia

Las reglas que miran varios mensajes de una sesión no se verifican en esta feature y quedan para
la spec del servidor (research R8): `hello` primero y `config` segundo (FR-008), `t_ms` no
decreciente (FR-010), `seq` desde 0 y sin saltos (FR-018), y un solo `run_finished` por `run_id`,
inmediatamente después de `off_track` (FR-025). Siguen siendo normativas: el texto del contrato
las enuncia.

## Estados

### Sesión

```text
(conexión) ──► abierta ──hello, config──► activa ──cierre de conexión──► terminada
                                           │  ▲
                                           └──┘ load aceptado (sin corrida) ──► hello, config
```

Solo hay una sesión por conexión; al terminar se pierde la corrida activa (FR-007). Un `load`
aceptado reemplaza el `hello` vigente de la sesión (FR-013).

### Corrida

```text
          start (acepta)                    stop  ─────────────┐
 inactiva ───────────────► activa ──────────────────────────────┤──► run_finished ──► inactiva
   ▲  run_started emitido  │  off_track ──► (off_track emitido) ┘
   │                       │  set_config ──► config_changed = true (sigue activa)
   │                       │  desconexión ──► sesión terminada (sin run_finished)
   └── start en activa ──► error run_active · stop en inactiva ──► error no_run
```

- Entrar en **activa** genera `run_id`, emite `run_started` y la telemetría pasa a `running=true`.
- Comandos solo-sim en **activa** → `error` `run_active` (FR-032).
- Salir de **activa** emite exactamente un `run_finished` (FR-025).
