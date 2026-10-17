# Contrato v1 de velocista-sim

**Revisión del documento**: 1.2 · **Versión del protocolo**: `v = 1` · **Fecha**: 2026-10-16

Este documento es la fuente de verdad de la interfaz externa de velocista-sim. Lo cumplen por
igual el simulador y el robot real (ESP32). Los clientes (front, backend, optimizador) se
desarrollan contra él, sin necesidad de tener el simulador en marcha.

El contrato tiene tres partes que se mantienen juntas:

- este texto, que es normativo;
- un JSON Schema (draft 2020-12) por mensaje, comando, perfil del robot y pista, en
  [`schemas/`](./schemas/);
- ejemplos válidos e inválidos, con el motivo esperado del rechazo, en [`examples/`](./examples/).

Las palabras MUST, MUST NOT y SHOULD se usan con el sentido de RFC 2119.

`contrato-v1.1-velocista-sim.pdf` era el borrador 1.1 y queda solo como referencia histórica.
Ante cualquier diferencia prevalece este documento.

## Propósito

Que todos los clientes reciban los mismos mensajes, con la misma semántica y las mismas
unidades, tanto si se conectan al simulador como al robot real. El lazo de control corre a bordo:
los clientes solo configuran y observan, nunca controlan ciclo a ciclo.

## Conexión

- La conexión es un único WebSocket en la ruta `/ws`
  (p. ej. `wss://<proyecto>.up.railway.app/ws?robot=velocista-01&track=oval-01`).
- Parámetros opcionales: `robot` (ID de perfil) y `track` (ID de pista). Si se omiten, el
  simulador usa un perfil y una pista por defecto. El robot real los ignora.
- Si `robot` o `track` no existen, el simulador envía `hello` y `config` con los valores por
  defecto y a continuación un `error` (`unknown_robot` o `unknown_track`). La conexión sigue
  abierta.
- Cada conexión crea una **sesión** propia e independiente, con su `session_id`. Lo que hace un
  cliente no afecta a otras sesiones.
- Al abrirse la sesión, el servidor MUST enviar `hello` y luego `config`, antes de cualquier
  otro mensaje.
- La sesión termina al cerrarse la conexión, y con ella cualquier corrida activa. No se conserva
  estado para reanudarla: reconectarse abre una sesión nueva con `session_id` nuevo. No se emite
  `run_finished`, porque no hay a quién enviarlo. El robot real MUST detener los motores al
  perder la conexión durante una corrida (FR-007).
- El contrato no define mensajes de keepalive propios. Las conexiones caídas se detectan con el
  ping/pong del propio WebSocket (FR-007a).

## Formato

- Cada frame de texto contiene **exactamente un** mensaje JSON codificado en UTF-8 (FR-009).
- Todo mensaje servidor→cliente lleva el envoltorio común (FR-010):

  | Campo | Tipo | Significado |
  |---|---|---|
  | `type` | string | `hello`, `config`, `telemetry`, `event`, `catalog` o `error` |
  | `v` | entero | Versión del protocolo: `1` |
  | `t_ms` | entero ≥ 0 | Milisegundos desde el inicio de la sesión; no decrece entre mensajes sucesivos |

- Todo comando cliente→servidor lleva `cmd` (string). `v` es opcional; si se envía y no es `1`,
  el servidor responde `error` `unsupported_version`. Los comandos no llevan `t_ms`, porque el
  cliente no conoce el reloj de la sesión (FR-011).
- Schema común: [`schemas/common.schema.json`](./schemas/common.schema.json).

## Unidades

Toda magnitud física se expresa en unidades SI: m, s, rad, m/s, rad/s, V, N. Las únicas
excepciones son las de esta tabla (FR-012):

| Magnitud | Unidad | Rango | Motivo |
|---|---|---|---|
| Tiempo (`t_ms`, `lap_ms`, `current_ms`, `*_lap_ms`, `motor_tau_ms`, `control_period_ms`) | ms | entero ≥ 0 | Resolución suficiente sin decimales |
| Lecturas de sensores de línea (`sensors`, `adc_white`, `adc_black`, `adc_noise`) | cuentas ADC crudas | 0 … 2^`adc_bits` − 1 | Es lo que mide el robot, sin calibrar |
| `line_position` y `error` | milésimas de sensor | `line_position`: 0 … (`line_sensors` − 1) × 1000 | Convención del controlador a bordo |
| PWM de motores (`motors.left`, `motors.right`, `base_speed`) | PWM | −255 … 255 (`base_speed`: 0 … 255) | Es lo que aplica el controlador |

Una unidad no SI que no figure en esta tabla está prohibida.

## Versionado

- Agregar un campo opcional, un código de error o un valor nuevo a un conjunto abierto **no**
  cambia `v` (FR-005).
- Renombrar o quitar un campo, o cambiar su tipo, unidad o significado, MUST incrementar `v`.
- Los receptores MUST ignorar los campos desconocidos. Por eso ningún schema restringe
  `additionalProperties`.
- Consecuencia aceptada: un campo opcional mal escrito (p. ej. `battery_vv`) no se detecta como
  sobrante. Un obligatorio mal escrito sí, porque se informa que falta.

## Elementos solo-sim

Estos elementos existen solo en el simulador. Todo lo demás es idéntico con el robot real, y un
cliente MUST poder funcionar ignorándolos por completo.

| Elemento | Tipo | Con el robot real |
|---|---|---|
| `sim_truth` | campo de `telemetry` | Ausente (`source = "robot"`) |
| `reset` | comando | `error` `sim_only` |
| `load` | comando | `error` `sim_only` |
| `set_profile` | comando | `error` `sim_only` |
| `load_track` | comando | `error` `sim_only` |

## Mensajes

Mensajes servidor→cliente. Todos llevan el envoltorio común (`type`, `v`, `t_ms`), que no se
repite en las tablas.

### Cuándo se envía cada mensaje

| Mensaje | Cuándo | Requisito |
|---|---|---|
| `hello` | Al abrirse la sesión, y de nuevo tras cada `load` aceptado. Siempre seguido de un `config` | FR-008, FR-013 |
| `config` | Al abrirse la sesión (después de `hello`) y tras cada cambio aceptado de configuración, frecuencia, perfil o pista | FR-008, FR-016 |
| `telemetry` | Periódicamente a `rate_hz` (por defecto 50 Hz, cada 20 ms) mientras la conexión esté abierta, haya o no corrida | FR-017 |
| `event` | Al instante, cuando ocurre: `run_started`, `lap`, `off_track`, `run_finished` | FR-022 a FR-025 |
| `catalog` | Solo como respuesta a `list` | FR-026 |
| `error` | Cuando un comando es inválido o no aplica | FR-027 |

Los datos de `hello` describen qué información llega en el resto de los mensajes. Todo mensaje
MUST interpretarse y validarse con el **último** `hello` recibido en la sesión. `load` es el único
comando que puede cambiarlos (FR-013).

### `hello`

Describe el robot. Schema: [`messages/hello.schema.json`](./schemas/messages/hello.schema.json) ·
Ejemplos: [`valid/hello/`](./examples/valid/hello/), [`invalid/hello/`](./examples/invalid/hello/).

| Campo | Tipo | Rango / valores | Obligatorio |
|---|---|---|---|
| `session_id` | string | no vacío | Sí |
| `source` | string | `"sim"` o `"robot"` | Sí |
| `robot.id`, `robot.firmware`, `robot.hw_rev` | string | no vacíos | Sí |
| `capabilities.line_sensors` | entero | ≥ 1 (defecto v1: 16) | Sí |
| `capabilities.adc_bits` | entero | 8–16 (defecto v1: 12) | Sí |
| `capabilities.motors` | entero | `2` (fijo en v1) | Sí |
| `capabilities.turbine` | booleano | defecto v1: `false` | Sí |
| `capabilities.encoders` | booleano | defecto v1: `false` | Sí |
| `capabilities.imu` | booleano | defecto v1: `false` | Sí |
| `capabilities.lap_timing` | booleano | `true` en el simulador; `false` en el robot real v1 | Sí |
| `capabilities.battery.cells` | entero | ≥ 1 (defecto v1: 2) | Sí |
| `capabilities.battery.nominal_v` | número (V) | > 0 (defecto v1: 7.4) | Sí |
| `capabilities.battery.voltage_sense` | booleano | `true` en el simulador | Sí |

`hello` incluye solo los datos que cambian qué información llega a los clientes. Los parámetros
físicos del perfil no van en `hello` (FR-014).

### `config`

Configuración vigente del controlador y de la sesión. Schema:
[`messages/config.schema.json`](./schemas/messages/config.schema.json) · Ejemplos:
[`valid/config/`](./examples/valid/config/), [`invalid/config/`](./examples/invalid/config/).

| Campo | Tipo | Unidad / rango | Obligatorio |
|---|---|---|---|
| `controller` | string | en v1 solo `"pid"` | Sí |
| `params.kp`, `params.ki`, `params.kd` | número | ≥ 0 | Sí |
| `base_speed` | entero | PWM 0–255 | Sí |
| `rate_hz` | entero | Hz, 10–100 | Sí |
| `track_id` | string o `null` | `null` si no hay pista; el robot real envía `null` | Sí |

### `telemetry`

Estado del robot en cada ciclo de telemetría. Schema:
[`messages/telemetry.schema.json`](./schemas/messages/telemetry.schema.json) · Ejemplos:
[`valid/telemetry/`](./examples/valid/telemetry/), [`invalid/telemetry/`](./examples/invalid/telemetry/).

| Campo | Tipo | Unidad / rango | Presencia |
|---|---|---|---|
| `seq` | entero | ≥ 0 | Siempre |
| `run_id` | string | no vacío | Si y solo si `running = true` |
| `running` | booleano | | Siempre |
| `sensors` | array de enteros | ADC crudo, 0 … 2^`adc_bits` − 1; longitud = `capabilities.line_sensors` | Siempre |
| `line_position` | entero | milésimas de sensor, 0 … (`line_sensors` − 1) × 1000 | Siempre |
| `line_lost` | booleano | | Siempre |
| `error` | entero | `line_position` − centro, con centro = (`line_sensors` − 1) × 500 (7500 con 16 sensores) | Siempre |
| `control.p`, `control.i`, `control.d`, `control.out` | número | términos del PID y salida | Siempre |
| `motors.left`, `motors.right` | entero | PWM −255…255 aplicado en ese instante | Siempre |
| `lap.n`, `lap.current_ms` | entero | `n` ≥ 0; `current_ms` ms ≥ 0 | Si y solo si hay corrida activa y `lap_timing = true` |
| `battery_v` | número | V, > 0 | Si y solo si `battery.voltage_sense = true` |
| `odometry` | objeto | ver abajo | Si y solo si `encoders` o `imu` |
| `sim_truth` | objeto | ver abajo | Si y solo si `source = "sim"` (solo-sim) |

"Si y solo si" significa: con la condición cumplida, el campo MUST estar en **cada**
`telemetry`; sin ella, MUST estar ausente.

- **`seq`**: es por sesión. Empieza en 0 con el primer `telemetry`, aumenta de a 1 y nunca se
  reinicia, tampoco al iniciar corridas. Un salto indica mensajes perdidos; el cliente no debe
  esperar que se reenvíen (FR-018).
- **`odometry`** (FR-019): con `encoders = true` incluye `distance_m` (m, ≥ 0) y `speed_mps`
  (m/s); con `encoders = false` no los incluye. Con `imu = true` incluye `heading_rad` (rad); con
  `imu = false` no lo incluye.
- **`sim_truth`** (FR-020): `x`, `y` (m), `theta` (rad), `speed_mps` (m/s) y `distance_m` (m), la
  verdad exacta del simulador. Ningún comportamiento que deba funcionar con el robot real puede
  depender de él.
- Ningún mensaje servidor→cliente contiene la geometría de la pista, solo su `track_id` (FR-021).

### `event`

Eventos de la corrida. Schema: [`messages/event.schema.json`](./schemas/messages/event.schema.json)
· Ejemplos: [`valid/event/`](./examples/valid/event/), [`invalid/event/`](./examples/invalid/event/).

Todos los eventos llevan `event` (`run_started`, `lap`, `off_track` o `run_finished`) y `run_id`.

| `event` | Campos propios | Cuándo |
|---|---|---|
| `run_started` | — | Al aceptar `start` |
| `lap` | `lap` (entero ≥ 1, vuelta completada), `lap_ms` (entero > 0, ms) | Al completar una vuelta, solo si `lap_timing = true` |
| `off_track` | `reason` (en v1: `"line_lost"`) | Al salir de la pista |
| `run_finished` | `summary` (ver abajo) | Al terminar la corrida |

Campos de `summary` (todos obligatorios, FR-023):

| Campo | Tipo | Valor |
|---|---|---|
| `laps` | entero ≥ 0 o `null` | Entero si `lap_timing = true`; `null` si `lap_timing = false` |
| `best_lap_ms`, `avg_lap_ms` | entero > 0 o `null` | Entero si `laps ≥ 1`; `null` si `laps` es `0` o `null` |
| `off_tracks` | entero ≥ 0 | Salidas de pista en la corrida |
| `track_id` | string o `null` | Pista de la corrida |
| `config` | objeto | `controller`, `params`, `base_speed`, con la forma de `config`: la configuración con la que **empezó** la corrida |
| `config_changed` | booleano | `true` si se aceptó algún `set_config` durante la corrida |

Reglas de la corrida (FR-024, FR-025):

- Una corrida va desde `start` hasta `stop` o una salida de pista. En ambos casos se emite
  **exactamente un** `run_finished` para ese `run_id`. Tras `off_track`, el `run_finished` llega
  inmediatamente después.
- `run_started` y `run_finished` se emiten siempre, también con el robot real.
- `lap` es opcional: solo existe con `lap_timing = true`. Los clientes MUST funcionar sin recibir
  nunca `event lap` ni el bloque `lap` de la telemetría (FR-024a).

### `catalog`

Robots y pistas disponibles. Schema:
[`messages/catalog.schema.json`](./schemas/messages/catalog.schema.json) · Ejemplos:
[`valid/catalog/`](./examples/valid/catalog/), [`invalid/catalog/`](./examples/invalid/catalog/).

| Campo | Tipo | Obligatorio |
|---|---|---|
| `robots` | array de strings no vacíos, sin repetidos | Sí |
| `tracks` | array de strings no vacíos, sin repetidos | Sí |

El robot real responde con `robots = [su propio id]` y `tracks = []` (FR-026).

### `error`

Respuesta a un comando inválido o que no aplica. Schema:
[`messages/error.schema.json`](./schemas/messages/error.schema.json) · Ejemplos:
[`valid/error/`](./examples/valid/error/), [`invalid/error/`](./examples/invalid/error/).

| Campo | Tipo | Obligatorio |
|---|---|---|
| `code` | string, uno de la tabla siguiente | Sí |
| `message` | string en español, legible por personas | Sí |
| `cmd` | string: comando que se rechaza | Si el error responde a un comando identificable |

| `code` | Cuándo |
|---|---|
| `invalid_json` | El frame no es JSON válido o no es un objeto |
| `unknown_cmd` | Falta `cmd` o su valor no es un comando del contrato |
| `invalid_params` | Faltan campos obligatorios, sobran combinaciones inválidas, un tipo es incorrecto o `set_profile` intenta cambiar un parámetro de `hello` |
| `out_of_range` | Un valor tiene el tipo correcto pero está fuera de rango (p. ej. `set_rate` con `hz = 150`) |
| `sim_only` | Comando solo-sim enviado al robot real |
| `run_active` | `start` con corrida activa, o comando solo-sim durante una corrida |
| `no_run` | `stop` sin corrida activa |
| `unknown_robot` | `robot` de la conexión o `robot_id` de `load` no existe |
| `unknown_track` | `track` de la conexión no existe |
| `invalid_track` | La pista de `load_track` no cumple track v1 |
| `unsupported_version` | El comando trae un `v` distinto de `1` |

Agregar un código nuevo es un cambio compatible. Los clientes MUST tratar un `code` desconocido
como error genérico.

## Comandos

Comandos cliente→servidor. Todos llevan `cmd` y, opcionalmente, `v` (que debe ser `1`). Solo
configuran u ordenan corridas: ningún comando actúa como control en tiempo real (FR-029).
Schemas en [`schemas/commands/`](./schemas/commands/); ejemplos en
[`valid/commands/`](./examples/valid/commands/) e [`invalid/commands/`](./examples/invalid/commands/),
una carpeta por comando.

### Reglas comunes

- Un comando rechazado responde `error` (con `cmd` si el comando es identificable) y **no
  produce ningún efecto** en la sesión (FR-027, FR-028).
- El `code` del `error` sigue la tabla de [`error`](#error): JSON inválido → `invalid_json`;
  `cmd` ausente o desconocido → `unknown_cmd`; `v` distinto de `1` → `unsupported_version`; campo
  obligatorio ausente, combinación inválida o tipo incorrecto → `invalid_params`; tipo correcto
  pero fuera de rango → `out_of_range`.
- Todo cambio aceptado de configuración, frecuencia, perfil o pista se confirma con un `config`
  completo (FR-016).

### Comandos generales

Valen igual en el simulador y en el robot real.

| `cmd` | Campos | Efecto | Robot real | Schema |
|---|---|---|---|---|
| `start` | — | Inicia una corrida con un `run_id` nuevo y emite `event run_started` | Sí | [`start`](./schemas/commands/start.schema.json) |
| `stop` | — | Detiene la corrida activa y emite `event run_finished` | Sí | [`stop`](./schemas/commands/stop.schema.json) |
| `set_config` | `controller` (`"pid"`), `params` (`kp`, `ki`, `kd`: números ≥ 0), `base_speed` (entero, PWM 0–255); todos opcionales, al menos uno | Cambia la configuración del controlador; los campos omitidos (y los parámetros omitidos dentro de `params`) conservan su valor. Responde `config` | Sí | [`set_config`](./schemas/commands/set_config.schema.json) |
| `set_rate` | `hz` (entero, 10–100) | Cambia la frecuencia de telemetría. Responde `config` con el nuevo `rate_hz` | Sí | [`set_rate`](./schemas/commands/set_rate.schema.json) |
| `list` | — | Responde `catalog` | Sí: `robots = [su propio id]`, `tracks = []` (FR-026) | [`list`](./schemas/commands/list.schema.json) |

Ejemplos:

```json
{"cmd": "start"}
{"cmd": "set_config", "controller": "pid", "params": {"kp": 0.045, "ki": 0, "kd": 0.9}, "base_speed": 180}
{"cmd": "set_config", "params": {"kp": 0.05}}
{"cmd": "set_rate", "hz": 20}
```

### Corridas

- `start` con una corrida activa responde `error` `run_active`; la corrida en curso continúa sin
  cambios. `stop` sin corrida activa responde `error` `no_run`, y no se emite `run_finished`
  (FR-031).
- Cada corrida recibe un `run_id` único dentro de la sesión. Para identificar una corrida fuera de
  la sesión (p. ej. al guardarla en el backend) se usa el par (`session_id`, `run_id`) (FR-033).
- Al iniciarse la corrida se emite `run_started` y la telemetría pasa a `running = true` con ese
  `run_id`. Al terminar (por `stop` o por salida de pista) se emite exactamente un
  `run_finished` y la telemetría vuelve a `running = false`, sin `run_id` (FR-025).
- `set_config` aceptado durante una corrida se aplica **al instante** (al comienzo del siguiente
  paso de control) y emite un `config` nuevo. La corrida queda marcada con
  `summary.config_changed = true`, y `summary.config` sigue siendo la configuración con la que
  empezó. El optimizador MUST descartar las corridas con `config_changed = true` (FR-034).

Estados de una corrida:

```text
          start (acepta)                    stop  ─────────────┐
 inactiva ───────────────► activa ──────────────────────────────┤──► run_finished ──► inactiva
   ▲  run_started emitido  │  off_track ──► (off_track emitido) ┘
   │                       │  set_config ──► config_changed = true (sigue activa)
   │                       │  desconexión ──► sesión terminada (sin run_finished)
   └── start en activa ──► error run_active · stop en inactiva ──► error no_run
```

Ciclo del optimizador: `set_config` → `start` → (telemetría, eventos) → `run_finished` →
leer `summary` → siguiente `set_config`. Como `summary.config` tiene la misma forma que
`set_config`, se puede reenviar tal cual (agregándole `"cmd": "set_config"`).

### Comandos solo-sim

Existen solo en el simulador. El robot real responde a todos con `error` `sim_only` y nada cambia
(FR-030). En el simulador, si hay una corrida activa responden `error` `run_active`: se deben
enviar con la corrida detenida (FR-032).

| `cmd` | Campos | Efecto | Schema |
|---|---|---|---|
| `reset` | — | Vuelve el robot a la línea de salida | [`reset`](./schemas/commands/reset.schema.json) |
| `load` | `robot_id` (string) | Cambia el perfil de robot. El servidor reenvía `hello` y luego `config`; desde ahí todo se interpreta con el nuevo `hello`. Es el **único** comando que cambia datos de `hello` (FR-013). `robot_id` inexistente → `error` `unknown_robot` | [`load`](./schemas/commands/load.schema.json) |
| `set_profile` | `measured` (objeto: parámetro → valor o `null`) | Fija (valor) o borra (`null`) valores medidos de parámetros físicos y de calibración. Responde `config` | [`set_profile`](./schemas/commands/set_profile.schema.json) |
| `load_track` | `track` (pista [track v1](#pista-track-v1)) | Carga la pista en el mundo. Responde `config` con el `track_id` de la pista. Pista inválida → `error` `invalid_track` | [`load_track`](./schemas/commands/load_track.schema.json) |

Reglas de `set_profile` (FR-037):

- Solo acepta los 12 parámetros físicos y de calibración (ver [Perfil del robot](#perfil-del-robot)):
  `sensor_pitch_m`, `sensor_offset_m`, `adc_white`, `adc_black`, `adc_noise`, `max_speed_mps`,
  `motor_tau_ms`, `wheelbase_m`, `max_lateral_accel_mps2`, `turbine_suction_n`,
  `encoder_ticks_per_rev` y `control_period_ms`.
- Un parámetro de `hello` o un parámetro inexistente → `error` `invalid_params`. Para cambiar un
  parámetro de `hello` hay que cargar otro perfil con `load`.
- Un valor con tipo incorrecto → `invalid_params`; con tipo correcto pero fuera de rango →
  `out_of_range`. Cada valor tiene el rango de su parámetro.
- Se aplica **todo o nada**: si un parámetro se rechaza, no cambia ninguno.

Ejemplos:

```json
{"cmd": "reset"}
{"cmd": "load", "robot_id": "velocista-01"}
{"cmd": "set_profile", "measured": {"wheelbase_m": 0.128}}
{"cmd": "set_profile", "measured": {"wheelbase_m": null}}
{"cmd": "load_track", "track": {"id": "oval-small", "v": 1, "...": "..."}}
```

## Perfil del robot

Parámetros con que el simulador modela el robot. Schema:
[`robot-profile.schema.json`](./schemas/robot-profile.schema.json) · Ejemplos:
[`valid/robot-profile/`](./examples/valid/robot-profile/),
[`invalid/robot-profile/`](./examples/invalid/robot-profile/).

Cada parámetro tiene la forma (FR-035):

```json
"wheelbase_m": {"default": 0.130, "measured": null, "source": "estimated"}
```

| Campo | Significado |
|---|---|
| `default` | Valor por defecto |
| `measured` | Valor medido en el robot real, del mismo tipo y rango que `default`, o `null` si no se midió |
| `source` | Origen del valor por defecto: `defined` (definido por el equipo), `datasheet`, `estimated` o `current_robot` (tomado del robot actual) |

El **valor efectivo** de cada parámetro es `measured` si no es `null`; si no, `default`. El
simulador usa siempre el valor efectivo. En Python: `velocista_sim.contract.effective_profile`.

Parámetros del perfil v1 (FR-036). Los que tienen campo en `hello` son **parámetros de `hello`**
(solo cambian con `load`); el resto son **parámetros físicos y de calibración** (los que acepta
`set_profile`).

| Parámetro | Tipo / rango | Unidad | Defecto v1 | `source` | Campo en `hello` |
|---|---|---|---|---|---|
| `id` | string no vacío (sin `measured`: siempre `null`) | — | `velocista-01` | defined | `robot.id` |
| `firmware` | string no vacío | — | `sim-0.1` | defined | `robot.firmware` |
| `hw_rev` | string no vacío | — | `A` | defined | `robot.hw_rev` |
| `line_sensors` | entero ≥ 1 | — | 16 | current_robot | `capabilities.line_sensors` |
| `adc_bits` | entero 8–16 | — | 12 | current_robot | `capabilities.adc_bits` |
| `sensor_pitch_m` | número > 0 | m | 0.009525 | datasheet | — |
| `sensor_offset_m` | número > 0 (regleta delante del eje) | m | 0.085 | estimated | — |
| `adc_white` | entero 0–65535 | ADC | 200 | estimated | — |
| `adc_black` | entero 0–65535 | ADC | 3900 | estimated | — |
| `adc_noise` | entero ≥ 0 | ADC (±) | 60 | estimated | — |
| `motors` | `2` (fijo en v1) | — | 2 | current_robot | `capabilities.motors` |
| `max_speed_mps` | número > 0 (a PWM 255) | m/s | 2.8 | estimated | — |
| `motor_tau_ms` | número > 0 | ms | 45 | estimated | — |
| `wheelbase_m` | número > 0 | m | 0.130 | estimated | — |
| `max_lateral_accel_mps2` | número > 0 | m/s² | 9.0 | estimated | — |
| `turbine` | booleano | — | `false` | current_robot | `capabilities.turbine` |
| `turbine_suction_n` | número ≥ 0 o `null` (sin turbina) | N | `null` | current_robot | — |
| `encoders` | booleano | — | `false` | current_robot | `capabilities.encoders` |
| `encoder_ticks_per_rev` | entero ≥ 1 o `null` (sin encoders) | ticks | `null` | current_robot | — |
| `imu` | booleano | — | `false` | current_robot | `capabilities.imu` |
| `battery_cells` | entero ≥ 1 | — | 2 | estimated | `capabilities.battery.cells` |
| `battery_nominal_v` | número > 0 | V | 7.4 | estimated | `capabilities.battery.nominal_v` |
| `battery_voltage_sense` | booleano | — | `true` | estimated | `capabilities.battery.voltage_sense` |
| `lap_timing` | booleano | — | `true` | defined | `capabilities.lap_timing` |
| `control_period_ms` | número > 0 | ms | 2 | estimated | — |

El perfil puede tener parámetros adicionales; los receptores los ignoran (FR-005).

## Pista track v1

Formato con que el trazador exporta una pista y `load_track` la envía al simulador. Solo la
recibe el **mundo** simulado: ningún mensaje servidor→cliente contiene su geometría, solo su
`track_id` (FR-021). Schema: [`track.schema.json`](./schemas/track.schema.json) · Ejemplos:
[`valid/track/`](./examples/valid/track/), [`invalid/track/`](./examples/invalid/track/).

| Campo | Tipo / rango | Significado |
|---|---|---|
| `id` | string no vacío | ID de la pista; es el `track_id` de `config` |
| `v` | `1` | Versión del formato de pista |
| `name` | string | Nombre legible |
| `units` | `"m"` | Unidades de todas las longitudes |
| `board.width`, `board.height` | número > 0, m | Tablero: ocupa `[0, width] × [0, height]` |
| `line_width` | número > 0, m | Ancho de la línea |
| `closed` | booleano | `true` si el último punto se une con el primero |
| `centerline` | array de ≥ 2 puntos `[x, y]`, m | Línea central muestreada cada 0,005 m |
| `gaps` | array (posiblemente vacío) de `{at, length}`: `at` ≥ 0, `length` > 0, m | Cortes de la línea |
| `start.at` | número ≥ 0, m | Línea de salida |
| `rules_profile` | string no vacío | Perfil de **reglamento** del trazador (no es el perfil del robot) |
| `marks` | cualquiera | Reservado para marcas laterales en una versión posterior; en v1 su presencia no invalida la pista pero no tiene efecto (FR-040) |

Geometría (FR-038, FR-039):

- **Coordenadas**: metros, con origen en la esquina inferior izquierda del tablero, x hacia la
  derecha e y hacia arriba (el mismo sistema que el trazador).
- **Posiciones a lo largo de la línea** (`gaps[].at`, `start.at`): distancia en metros recorrida
  sobre `centerline` desde el primer punto.
- **Longitud** de `centerline`: suma de las distancias entre puntos consecutivos, más el tramo
  último → primero si `closed = true`.
- Reglas que la pista MUST cumplir, con el identificador que usa el validador:

  | Regla | Condición |
  |---|---|
  | `track_at_range` | Todo `at` está entre 0 y la longitud de `centerline` |
  | `track_point_outside_board` | Todo punto de `centerline` está dentro del tablero |
  | `track_gaps_overlap` | Los intervalos `[at, at + length)` de los `gaps` no se superponen |
  | `track_sampling` | La distancia entre puntos consecutivos es 0,005 m ± 10 % (4,5–5,5 mm), sin contar el tramo de cierre |

Ejemplo abreviado (PDF v1.1, §7):

```json
{"id": "junior-02", "v": 1, "name": "Técnica 3 × 2,5", "units": "m",
 "board": {"width": 3.00, "height": 2.50},
 "line_width": 0.019, "closed": true,
 "centerline": [[0.500, 0.450], [0.505, 0.450], "…"],
 "gaps": [{"at": 4.82, "length": 0.02}],
 "start": {"at": 0.70},
 "rules_profile": "lgr2026"}
```

## Paridad simulador–robot real

Un cliente conectado al robot real observa los mismos mensajes, con la misma semántica y las
mismas unidades, que conectado al simulador. Las únicas diferencias son los
[elementos solo-sim](#elementos-solo-sim) y los campos que dependen de lo que el robot declara
en `hello`. Esta sección resume qué MUST emitir y qué MUST NOT emitir el firmware.

### Campos condicionados

Cada campo condicionado está presente **si y solo si** se cumple su condición: con la condición,
MUST estar en **cada** mensaje; sin ella, MUST estar ausente (FR-018). El validador informa
cada caso con la regla indicada.

| Campo | Obligatorio si | Prohibido si | Reglas |
|---|---|---|---|
| `telemetry.odometry` | `encoders = true` o `imu = true` | `encoders = false` e `imu = false` | `odometry_missing` · `odometry_without_capability` |
| `telemetry.odometry.distance_m`, `.speed_mps` | `encoders = true` | `encoders = false` | `odometry_encoder_fields_missing` · `odometry_encoder_fields` |
| `telemetry.odometry.heading_rad` | `imu = true` | `imu = false` | `odometry_imu_fields_missing` · `odometry_imu_fields` |
| `telemetry.battery_v` | `battery.voltage_sense = true` | `battery.voltage_sense = false` | `battery_v_missing` · `battery_without_sense` |
| `telemetry.sim_truth` | `source = "sim"` | `source = "robot"` | `sim_truth_missing` · `sim_truth_without_sim` |
| `telemetry.lap` | `lap_timing = true` y `running = true` | `lap_timing = false`, o `running = false` | `lap_missing` · `lap_without_timing` (y `not` del schema sin corrida) |
| `telemetry.run_id` | `running = true` | `running = false` | `required` · `not` (schema) |
| `event` con `event = "lap"` | — (cuando se completa una vuelta) | `lap_timing = false` | `lap_without_timing` |
| `summary.laps` | entero (no `null`) si `lap_timing = true` | no `null` si `lap_timing = false` | `summary_laps_missing` · `summary_laps_without_timing` |
| `summary.best_lap_ms`, `.avg_lap_ms` | entero > 0 si `laps ≥ 1` | no `null` si `laps` es `0` o `null`, o si `lap_timing = false` | `type`/`const` (schema) · `summary_laps_without_timing` |

Si falta `odometry` entera, o llega sin capacidad, solo se informa la regla del bloque, no las
de sus campos. Las reglas de longitud y rango de `sensors`, `line_position` y `error`
(`sensors_length`, `sensor_range`, `line_position_range`, `error_consistency`) también dependen
de `hello` y valen igual para ambos.

El contexto es siempre el **último** `hello` de la sesión. Con el robot real ese `hello` no
cambia (no acepta `load`).

### Comportamiento del robot real

- **Motores**: v1 admite exactamente dos motores; `capabilities.motors` es `2` y `telemetry.motors`
  trae `left` y `right`.
- **Comandos solo-sim** (`reset`, `load`, `set_profile`, `load_track`): responde `error` con
  `code = "sim_only"` y `cmd` con el comando; nada cambia (FR-030).
- **`list`**: responde `catalog` con `robots = [su propio robot.id]` y `tracks = []`
  (FR-026; reglas `catalog_robot_real`).
- **`config.track_id`** y **`summary.track_id`**: siempre `null`, porque el robot real no conoce
  pistas (FR-015; regla `track_id_robot_real` en `config`).
- **Parámetros de conexión** `robot` y `track`: los ignora (FR-006).
- **Corridas**: emite `run_started` al aceptar `start` y `run_finished` al terminar, igual que el
  simulador (FR-024). En v1 declara `lap_timing = false`: no emite `event lap` ni el bloque `lap`,
  y `summary.laps`, `best_lap_ms` y `avg_lap_ms` son `null`. La detección de vueltas (marcas
  laterales o cronómetro de meta) queda para una spec futura.
- **Desconexión**: si pierde la conexión durante una corrida, MUST detener los motores. La corrida
  se pierde y no se emite `run_finished` (FR-007).

### Requisitos para los clientes

- Los clientes MUST funcionar correctamente sin recibir nunca `event lap` ni el bloque `lap` de
  la telemetría (FR-024a).
- Los clientes MUST poder funcionar ignorando por completo `sim_truth` y los comandos solo-sim.
- Ningún comportamiento que deba funcionar con el robot real puede depender de `sim_truth`
  (FR-020).

Ejemplos del robot real: [`valid/hello/robot-real.json`](./examples/valid/hello/robot-real.json),
[`valid/telemetry/robot-real.json`](./examples/valid/telemetry/robot-real.json),
[`valid/event/robot-real-run-finished.json`](./examples/valid/event/robot-real-run-finished.json),
[`valid/catalog/robot-real.json`](./examples/valid/catalog/robot-real.json) y
[`valid/config/robot-real.json`](./examples/valid/config/robot-real.json).

## Cambios respecto del PDF v1.1

El borrador 1.1 no tenía implementaciones, así que estos cambios se consideran correcciones del
borrador y no suben `v`:

| Cambio | Tipo | Motivo |
|---|---|---|
| `capabilities.lap_timing` en `hello` | Campo nuevo | Que `lap` sea opcional sin romper la paridad |
| `capabilities.battery.voltage_sense` en `hello` | Campo nuevo | El PDF condicionaba `battery_v` a algo que `hello` no declaraba |
| `capabilities.motors` fijo en `2` | Restricción | v1 solo admite `motors.left` y `motors.right` |
| `code` en `error` | Campo nuevo | Conjunto cerrado de códigos para que los clientes reaccionen sin leer el texto |
| `cmd` en `error` | Campo nuevo | Identifica el comando que se rechaza |
| `summary.config_changed` en `run_finished` | Campo nuevo | Marca corridas con `set_config` a mitad de camino |
| Forma de `summary.config` | Corrección | Igual que en `config` (`controller`, `params`, `base_speed`); el PDF la mostraba plana |
| `v` obligatorio en `event` | Corrección | Los ejemplos del PDF lo omitían, pero el PDF exige `v` en todo mensaje |
| `summary.laps` no nulo con `lap_timing = true` | Precisión | `best_lap_ms` y `avg_lap_ms` son enteros > 0 si `laps ≥ 1` y `null` si `laps` es `0` o `null` |
| Campos condicionados obligatorios con su capacidad | Precisión | `odometry`, `battery_v`, `sim_truth` y `lap` están presentes **si y solo si** se cumple su condición |
| `hello` reenviado tras `load` | Precisión | `load` es el único comando que cambia datos de `hello`; se valida con el último `hello` |
| `set_profile` limitado | Restricción | Solo parámetros físicos y de calibración; los de `hello` requieren `load` |
| Valores de `source` del perfil en inglés | Corrección | `defined`, `datasheet`, `estimated`, `current_robot` (el PDF usaba `"estimado"`) |
| Origen de coordenadas de la pista | Precisión | Esquina inferior izquierda del tablero, x a la derecha, y hacia arriba |
| Tolerancia de muestreo de `centerline` | Precisión | 0,005 m ± 10 % entre puntos consecutivos |
