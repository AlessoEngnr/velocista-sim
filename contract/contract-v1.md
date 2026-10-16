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

Campos de `summary` (todos obligatorios):

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

<!-- Se completa con las historias de usuario 2 y 3. -->

## Perfil del robot

<!-- Se completa con la historia de usuario 3. -->

## Pista track v1

<!-- Se completa con la historia de usuario 3. -->

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
