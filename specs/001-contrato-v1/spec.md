# Especificación: Contrato v1 de mensajes entre velocista-sim y sus clientes

**Feature Branch**: `001-contrato-v1`

**Created**: 2026-10-16

**Status**: Draft

**Input**: Descripción del usuario: "Contrato v1 de mensajes entre velocista-sim y sus clientes. Formalizar el contrato de contract/contrato-v1.1-velocista-sim.pdf como especificación verificable: cada mensaje y comando con sus campos, tipos, unidades, rangos y cuándo se envía, para que front, backend y optimizador puedan desarrollar contra él sin el simulador, y para que el robot real (ESP32) lo implemente igual."

**Fuente**: `contract/contrato-v1.1-velocista-sim.pdf` (borrador v1.1, 15-oct-2026). Donde el borrador es
ambiguo o se contradice, esta especificación fija una decisión y la registra en *Supuestos*.

## Clarifications

### Session 2026-10-16

- Q: Con el robot real, ¿quién emite `run_started` y `lap`? → A: El robot emite `run_started` al recibir `start` y `run_finished` al terminar; `lap` es opcional (solo si puede detectarlo: marcas o cronómetro, spec futura). Los clientes MUST funcionar sin recibir `lap`. (FR-024, FR-024a)
- Q: ¿`set_config` durante una corrida aplica al instante o en la siguiente? → A: Al instante; `run_finished.summary` incluye `config_changed` y `summary.config` refleja la configuración con la que empezó la corrida; el optimizador descarta corridas con `config_changed=true`. (FR-023, FR-034)
- Q: ¿Códigos de error estandarizados? → A: Sí, conjunto cerrado de `code` además de `message`. (FR-027)
- Q: ¿Desconexión y keepalive? → A: Se pierden la sesión y la corrida (el robot real se detiene); el keepalive es el ping/pong de WebSocket. (FR-007, FR-007a)
- Q: ¿`seq` se reinicia por sesión o por corrida? → A: Por sesión; empieza en 0 y nunca se reinicia. (FR-018)

### Session 2026-10-16 (resolución del análisis)

- ¿Pueden cambiar los datos de `hello` a mitad de sesión? → Solo con `load`, tras el cual el servidor reenvía `hello` y luego `config`; `set_profile` rechaza los parámetros de `hello` con `invalid_params`; se valida siempre con el último `hello`. (FR-013, FR-029, FR-037)
- ¿Una capacidad declarada obliga a enviar su campo? → Sí: `odometry` (con sus campos según `encoders`/`imu`), `battery_v`, `sim_truth` y `lap` (con corrida activa) MUST estar en cada `telemetry` cuando su condición se cumple. (FR-018 a FR-020, FR-024)
- ¿Cuántos motores admite v1? → Exactamente 2 (`left`, `right`). (FR-013, FR-018)
- ¿Origen de coordenadas de la pista? → Esquina inferior izquierda del tablero, x a la derecha, y hacia arriba, en metros. (FR-038)
- Valores de `source` del perfil en inglés: `defined`, `datasheet`, `estimated`, `current_robot`. (FR-035)
- ¿Puede `summary.laps` ser `null` con `lap_timing = true`? → No; `best_lap_ms` y `avg_lap_ms` siguen la regla de `laps ≥ 1`. (FR-023, FR-024)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Desarrollar un cliente contra el contrato sin el simulador (Priority: P1)

Un integrante del equipo que desarrolla el front, el backend o el optimizador necesita saber con
exactitud qué mensajes recibirá (hello, config, telemetry, event, catalog, error), con qué campos,
tipos, unidades y rangos, y poder comprobar automáticamente si un mensaje dado (real o de prueba)
es válido, sin tener el simulador en marcha.

**Why this priority**: es el motivo principal de la feature: hoy el contrato es un PDF y cada cliente
lo interpreta por su cuenta. Sin una definición verificable de los mensajes salientes, ningún
cliente puede avanzar en paralelo.

**Independent Test**: tomar los ejemplos válidos e inválidos publicados para cada mensaje
servidor→cliente y verificar que la validación automática acepta todos los válidos y rechaza todos
los inválidos, indicando el motivo.

**Acceptance Scenarios**:

1. **Given** el ejemplo de `telemetry` del robot actual (16 sensores, sin encoders ni IMU), **When** se valida contra el contrato, **Then** resulta válido.
2. **Given** un `telemetry` con un valor de sensor de 5000, **When** se valida, **Then** se rechaza indicando que el campo excede el rango 0–4095.
3. **Given** un `telemetry` sin el campo `seq`, **When** se valida, **Then** se rechaza por falta de un campo obligatorio.
4. **Given** un `hello` con `capabilities.line_sensors = 16` y un `telemetry` con 15 valores en `sensors`, **When** se valida el telemetry en el contexto de ese hello, **Then** se rechaza por longitud incorrecta.
5. **Given** un mensaje con un campo adicional desconocido, **When** se valida, **Then** resulta válido (agregar campos no rompe clientes).

---

### User Story 2 - Controlar corridas y configuración igual en simulador y robot real (Priority: P2)

Un cliente (front u optimizador) inicia y detiene corridas, cambia la configuración del controlador
y la frecuencia de telemetría, y consulta robots y pistas disponibles, usando exactamente los mismos
comandos y recibiendo las mismas respuestas tanto si habla con el simulador como con el robot real.

**Why this priority**: es el ciclo de trabajo del optimizador (`set_config` → corre → lee
`run_finished`) y del front; depende de que los mensajes de la historia 1 estén definidos.

**Independent Test**: validar los ejemplos válidos e inválidos de los comandos `start`, `stop`,
`set_config`, `set_rate` y `list`, y los mensajes de la secuencia `set_config` → `start` → `stop`
(`config`, `event run_started`, telemetría con `running=true` y el mismo `run_id`,
`event run_finished` con su resumen), cada uno por separado. El comportamiento del servidor ante
esa secuencia y el orden de los mensajes se verifican en la spec del servidor.

**Acceptance Scenarios**:

1. **Given** una sesión recién abierta, **When** el cliente se conecta, **Then** recibe primero `hello` y luego `config`, ambos antes que cualquier `telemetry`.
2. **Given** una sesión sin corrida activa, **When** el cliente envía `start`, **Then** se genera un nuevo `run_id`, llega `event run_started` con ese `run_id` y la telemetría siguiente lo incluye con `running=true`.
3. **Given** una corrida activa, **When** el cliente envía `stop`, **Then** llega `event run_finished` con `summary` y la telemetría pasa a `running=false`.
4. **Given** una corrida activa, **When** el robot pierde la línea, **Then** llega `event off_track` seguido de `event run_finished` para el mismo `run_id`.
5. **Given** cualquier sesión, **When** el cliente envía `set_rate` con `hz=20`, **Then** recibe un `config` con `rate_hz=20` y la telemetría pasa a llegar cada 50 ms.
6. **Given** cualquier sesión, **When** el cliente envía `set_rate` con `hz=150`, **Then** recibe `error` con `code="out_of_range"` y la frecuencia no cambia.
7. **Given** una corrida iniciada con `kp=0.045`, **When** el cliente envía `set_config` con `kp=0.05` y luego `stop`, **Then** llega un `config` con `kp=0.05` al instante y el `run_finished.summary` trae `config.params.kp=0.045` y `config_changed=true`.

---

### User Story 3 - Cargar pistas y ajustar el perfil del robot en el simulador (Priority: P3)

Un cliente envía al simulador una pista en formato track v1 (exportada por el trazador), elige un
perfil de robot y registra valores medidos del robot real para que el simulador se le parezca cada
vez más. Al robot real esos comandos le devuelven error.

**Why this priority**: permite usar pistas reales y converger hacia el robot físico, pero el
simulador ya funciona con un perfil y una pista de ejemplo.

**Independent Test**: validar ejemplos válidos e inválidos de pista track v1, del perfil del robot
y de los comandos solo-sim, y del `error` con `code="sim_only"` que los rechaza en el robot real.
Que el servidor responda efectivamente esos errores se verifica en la spec del servidor.

**Acceptance Scenarios**:

1. **Given** una pista track v1 válida, **When** se envía con `load_track` al simulador, **Then** llega un `config` con el `track_id` de esa pista y ningún mensaje posterior contiene su geometría.
2. **Given** una pista con `centerline` de menos de 2 puntos, **When** se valida, **Then** se rechaza.
3. **Given** un perfil con `wheelbase_m` por defecto 0,130, **When** se envía `set_profile` con `measured.wheelbase_m = 0.128`, **Then** el perfil efectivo usa 0,128 y registra que el valor proviene de una medición.
4. **Given** una conexión con `source="robot"`, **When** se envía `reset`, `load`, `set_profile` o `load_track`, **Then** se recibe `error` y nada cambia.
5. **Given** el simulador, **When** se envía `set_profile` con `measured.line_sensors = 8`, **Then** se recibe `error` con `code="invalid_params"` porque `line_sensors` aparece en `hello` y solo `load` puede cambiarlo.
6. **Given** el simulador, **When** se envía `load` con otro `robot_id` existente, **Then** llegan un `hello` nuevo y luego un `config`, y la telemetría siguiente se interpreta con ese `hello`.

---

### User Story 4 - Implementar el contrato en el robot real (ESP32) (Priority: P4)

Quien programa el firmware del ESP32 necesita saber qué es obligatorio, qué es opcional según las
capacidades que declara, y qué nunca debe emitir, para que los clientes funcionen sin cambios al
pasar del simulador al robot.

**Why this priority**: el robot real llega después del simulador, pero el contrato debe dejarlo
resuelto desde ahora para no romper clientes.

**Independent Test**: validar mensajes de ejemplo con `source="robot"` y verificar que el validador
rechaza los que traen `sim_truth`, los que traen `odometry` sin encoders ni IMU declarados y los que
traen `battery_v` sin declarar medición de voltaje.

**Acceptance Scenarios**:

1. **Given** un `hello` con `source="robot"`, **When** un `telemetry` de esa sesión incluye `sim_truth`, **Then** se rechaza.
2. **Given** un `hello` con `encoders=false` e `imu=false`, **When** un `telemetry` incluye `odometry`, **Then** se rechaza.
3. **Given** un `hello` con `encoders=true`, **When** un `telemetry` incluye `odometry.distance_m` y `odometry.speed_mps`, **Then** es válido.
4. **Given** el robot real, **When** recibe `list`, **Then** responde `catalog` con `robots` igual a su propio ID y `tracks` vacío.
5. **Given** un `hello` con `lap_timing=false`, **When** un `telemetry` incluye el bloque `lap` o llega un `event lap`, **Then** se rechaza; un `run_finished` con `laps=null` es válido.
6. **Given** un `hello` con `encoders=true`, **When** un `telemetry` no incluye `odometry`, **Then** se rechaza: una capacidad declarada obliga a enviar su campo.

---

### Edge Cases

- **Mensaje no JSON o sin `cmd`**: el servidor responde `error` y mantiene la conexión abierta.
- **Comando desconocido** (`cmd` no listado): `error`; la sesión sigue igual.
- **`start` con una corrida activa** y **`stop` sin corrida activa**: ver FR-031.
- **Comandos solo-sim durante una corrida**: ver FR-032.
- **`set_config` durante una corrida**: aplica al instante, la corrida queda marcada con `config_changed=true` y el optimizador la descarta (ver FR-034).
- **Robot sin detección de vueltas**: no llegan `event lap` ni el bloque `lap` de la telemetría; los clientes funcionan igual (ver FR-024).
- **Parámetros de conexión desconocidos** (`robot` o `track` que no existen): el simulador envía `hello` y `config` con los valores por defecto y a continuación un `error` que identifica el ID desconocido.
- **`set_profile` con un parámetro inexistente, fuera de rango o que aparece en `hello`**: `error` `invalid_params` u `out_of_range`; el perfil no cambia (todo o nada, FR-037).
- **`load` aceptado**: el servidor reenvía `hello` y luego `config`; desde ese momento los mensajes se interpretan con el nuevo `hello` (FR-013).
- **Pérdida de `seq`**: un salto en `seq` indica mensajes perdidos; el cliente no debe asumir reenvío.
- **Desconexión durante una corrida**: la sesión y la corrida se pierden; no se emite `run_finished` porque no hay a quién enviarlo. El robot real se detiene por seguridad (ver FR-007).
- **Telemetría sin corrida**: se sigue enviando a la frecuencia configurada con `running=false` y sin `run_id`.

## Requirements *(mandatory)*

### Functional Requirements

#### Fuente de verdad y validación

- **FR-001**: El contrato MUST existir en el repositorio como texto descriptivo versionado más una definición validable automáticamente de cada mensaje servidor→cliente, cada comando cliente→servidor, el perfil del robot y el formato de pista track v1.
- **FR-002**: Para cada mensaje, comando, perfil y pista el contrato MUST incluir al menos un ejemplo válido y al menos un ejemplo inválido por cada regla relevante (campo obligatorio ausente, tipo incorrecto, fuera de rango, campo condicionado indebido), con el motivo esperado del rechazo.
- **FR-003**: La validación MUST poder ejecutarse sin el simulador ni el robot, solo con los mensajes a revisar.
- **FR-004**: Las reglas que dependen de `hello` (longitud de `sensors`, presencia de `odometry`, `battery_v`, `sim_truth`) MUST poder verificarse dado el `hello` de la sesión.
- **FR-005**: Los receptores MUST ignorar campos desconocidos; agregar un campo opcional no cambia `v`. Renombrar o quitar un campo, o cambiar su tipo, unidad o significado, MUST incrementar `v`.

#### Conexión y sesión

- **FR-006**: La conexión MUST ser un único WebSocket en la ruta `/ws`, con parámetros opcionales `robot` (ID de perfil) y `track` (ID de pista). El robot real los ignora.
- **FR-007**: Cada conexión MUST crear una sesión propia e independiente; lo que hace un cliente no afecta a otras sesiones. La sesión termina al cerrarse la conexión, y con ella cualquier corrida activa: no se conserva estado para reanudarla y reconectarse abre una sesión nueva con `session_id` nuevo. El robot real MUST detener los motores al perder la conexión durante una corrida.
- **FR-007a**: El contrato no define mensajes de keepalive propios; la detección de conexiones caídas MUST hacerse con el ping/pong del propio WebSocket.
- **FR-008**: Al abrirse la sesión el servidor MUST enviar `hello` y luego `config`, antes de cualquier otro mensaje.
- **FR-009**: Cada frame de texto MUST contener exactamente un mensaje JSON codificado en UTF-8.

#### Envoltorio común (servidor → cliente)

- **FR-010**: Todo mensaje servidor→cliente MUST incluir `type` (string, uno de: `hello`, `config`, `telemetry`, `event`, `catalog`, `error`), `v` (entero, `1` en esta versión) y `t_ms` (entero ≥ 0, milisegundos desde el inicio de la sesión, no decreciente entre mensajes sucesivos de la sesión).
- **FR-011**: Todo comando cliente→servidor MUST incluir `cmd` (string). `v` es opcional; si se envía y no es `1`, el servidor MUST responder `error`. Los comandos no llevan `t_ms`.
- **FR-012**: Toda magnitud física MUST expresarse en unidades SI, salvo las excepciones definidas por el contrato: tiempo en ms, lecturas de sensores en cuentas ADC crudas, `line_position` en milésimas de sensor y PWM en −255…255.

#### `hello` — al conectarse y tras cada `load` aceptado

- **FR-013**: El servidor MUST enviar `hello` al abrirse la sesión y de nuevo tras cada `load` aceptado (seguido en ambos casos de un `config`, FR-008, FR-016). Es el único momento en que pueden cambiar los datos de `hello`; todo mensaje posterior MUST interpretarse y validarse con el **último** `hello` recibido. `hello` MUST incluir `session_id` (string), `source` (`"sim"` o `"robot"`), `robot` (`id`, `firmware`, `hw_rev`: strings) y `capabilities` con:

  | Campo | Tipo | Rango / valores | Defecto v1 |
  |---|---|---|---|
  | `line_sensors` | entero | ≥ 1 | 16 |
  | `adc_bits` | entero | 8–16 | 12 |
  | `motors` | entero | `2` (fijo en v1) | 2 |
  | `turbine` | booleano | | `false` |
  | `encoders` | booleano | | `false` |
  | `imu` | booleano | | `false` |
  | `battery.cells` | entero | ≥ 1 | 2 |
  | `battery.nominal_v` | número (V) | > 0 | 7.4 |
  | `battery.voltage_sense` | booleano | | `true` en el simulador |
  | `lap_timing` | booleano | | `true` en el simulador; `false` en el robot real v1 |

- **FR-014**: `hello` MUST incluir solo los datos que cambian qué información llega a los clientes; los parámetros físicos del perfil no van en `hello`.

#### `config` — al conectarse y tras cada cambio de configuración

- **FR-015**: `config` MUST incluir `controller` (string; en v1 solo `"pid"`), `params` (objeto; para `pid`: `kp`, `ki`, `kd`, números ≥ 0), `base_speed` (entero, PWM 0–255), `rate_hz` (entero 10–100) y `track_id` (string, o `null` si no hay pista; el robot real envía `null`).
- **FR-016**: El servidor MUST enviar un `config` completo tras cada cambio aceptado de configuración, frecuencia, perfil o pista.

#### `telemetry` — periódica mientras la conexión esté abierta

- **FR-017**: El servidor MUST enviar `telemetry` a `rate_hz` (por defecto 50 Hz, cada 20 ms) mientras la conexión esté abierta, haya o no corrida.
- **FR-018**: `telemetry` MUST incluir:

  | Campo | Tipo | Unidad / rango | Notas |
  |---|---|---|---|
  | `seq` | entero ≥ 0 | | Por sesión: empieza en 0 con el primer `telemetry` de la sesión, aumenta de a 1 y nunca se reinicia (tampoco al iniciar corridas); un salto indica pérdida |
  | `run_id` | string | | Presente si y solo si `running=true` |
  | `running` | booleano | | |
  | `sensors` | array de enteros | 0 … 2^`adc_bits` − 1 | Longitud = `capabilities.line_sensors` |
  | `line_position` | entero | 0 … (`line_sensors` − 1) × 1000 | Centro = (`line_sensors` − 1) × 500 (7500 con 16) |
  | `line_lost` | booleano | | |
  | `error` | entero | | `line_position` − centro |
  | `control` | objeto | | Para `pid`: `p`, `i`, `d`, `out` (números) |
  | `motors` | objeto | `left`, `right`: entero −255…255 | Los dos obligatorios (v1: `capabilities.motors = 2`); PWM aplicado en ese instante |
  | `lap` | objeto | `n` entero ≥ 0, `current_ms` entero ≥ 0 | Presente si y solo si hay corrida activa y `lap_timing = true` |
  | `battery_v` | número | V, > 0 | Presente si y solo si `battery.voltage_sense = true` |
  | `odometry` | objeto | ver FR-019 | Presente si y solo si `encoders` o `imu` |
  | `sim_truth` | objeto | ver FR-020 | Presente si y solo si `source = "sim"` |

  "Presente si y solo si" significa: con la condición cumplida el campo MUST estar en **cada**
  `telemetry`; sin ella MUST estar ausente.

- **FR-019**: Con `encoders = true`, `odometry` MUST incluir `distance_m` (m) y `speed_mps` (m/s); con `encoders = false`, MUST NOT incluirlos. Con `imu = true`, `odometry` MUST incluir `heading_rad` (rad); con `imu = false`, MUST NOT incluirlo. Si ni encoders ni IMU están declarados, `odometry` MUST estar ausente.
- **FR-020**: `sim_truth` MUST incluir `x`, `y` (m), `theta` (rad), `speed_mps` (m/s) y `distance_m` (m). MUST estar presente en cada `telemetry` si `source = "sim"` y ausente si `source = "robot"`. Ningún comportamiento que deba funcionar con el robot real puede depender de él.
- **FR-021**: Los mensajes servidor→cliente MUST NOT contener la geometría de la pista; solo su `track_id`.

#### `event` — al instante

- **FR-022**: `event` MUST incluir `event` (uno de `run_started`, `lap`, `off_track`, `run_finished`) y `run_id`, además del envoltorio común.
- **FR-023**: `run_started` MUST emitirse al iniciar una corrida. `lap` MUST incluir `lap` (entero ≥ 1, número de vuelta completada) y `lap_ms` (entero > 0). `off_track` MUST incluir `reason` (en v1: `"line_lost"`). `run_finished` MUST incluir `summary` con `laps` (entero ≥ 0 si `lap_timing = true`; `null` si `lap_timing = false`), `best_lap_ms` y `avg_lap_ms` (entero > 0 si `laps ≥ 1`; `null` si `laps` es `0` o `null`), `off_tracks` (entero ≥ 0), `track_id` (string o `null`), `config` (`controller`, `params`, `base_speed`, con la misma forma que en `config`: la configuración con la que **empezó** la corrida) y `config_changed` (booleano: `true` si se aceptó algún `set_config` durante la corrida).
- **FR-024**: `run_started` y `run_finished` MUST emitirse siempre, también con el robot real: `run_started` al aceptar `start` y `run_finished` al terminar la corrida. `lap` es opcional: solo se emite si `capabilities.lap_timing = true`, y el robot real v1 declara `false`. El mecanismo de detección de vueltas en el robot real (marcas laterales o cronómetro de meta) queda para una spec futura. Con `lap_timing = false`, el bloque `lap` de `telemetry` MUST estar ausente y `summary.laps`, `best_lap_ms` y `avg_lap_ms` MUST ser `null`. Con `lap_timing = true`, `summary.laps` MUST NOT ser `null`, y `best_lap_ms` y `avg_lap_ms` siguen la regla de FR-023. Con `lap_timing = true` y corrida activa, el bloque `lap` MUST estar presente en cada `telemetry` (FR-018).
- **FR-024a**: Los clientes MUST funcionar correctamente sin recibir nunca `event lap` ni el bloque `lap` de la telemetría.
- **FR-025**: Una corrida MUST ir desde `start` hasta `stop` o una salida de pista; en ambos casos MUST emitirse exactamente un `run_finished` para ese `run_id`. Tras `off_track`, el `run_finished` MUST llegar inmediatamente después.

#### `catalog` y `error`

- **FR-026**: `catalog` MUST enviarse solo como respuesta a `list` e incluir `robots` y `tracks` (arrays de string). El robot real MUST responder con `robots = [su propio id]` y `tracks = []`.
- **FR-027**: `error` MUST enviarse cuando un comando es inválido o no aplica, e incluir `message` (string en español, legible por personas) y, si el error responde a un comando identificable, `cmd` con el nombre de ese comando. `error` MUST incluir además `code`, de este conjunto cerrado:

  | `code` | Cuándo |
  |---|---|
  | `invalid_json` | El frame no es JSON válido o no es un objeto |
  | `unknown_cmd` | Falta `cmd` o su valor no es un comando del contrato |
  | `invalid_params` | Faltan campos obligatorios, sobran combinaciones inválidas, un tipo es incorrecto o `set_profile` intenta cambiar un parámetro de `hello` (FR-037) |
  | `out_of_range` | Un valor tiene el tipo correcto pero está fuera de rango (p. ej. `set_rate` con `hz=150`) |
  | `sim_only` | Comando solo-sim enviado al robot real |
  | `run_active` | Ver FR-031 y FR-032 |
  | `no_run` | Ver FR-031 |
  | `unknown_robot` | `robot` de la conexión o `robot_id` de `load` no existe |
  | `unknown_track` | `track` de la conexión no existe |
  | `invalid_track` | La pista de `load_track` no cumple track v1 |
  | `unsupported_version` | El comando trae un `v` distinto de `1` |

  Agregar un código nuevo es un cambio compatible; los clientes MUST tratar un `code` desconocido como error genérico.
- **FR-028**: Un comando rechazado MUST NOT producir ningún efecto en la sesión.

#### Comandos (cliente → servidor)

- **FR-029**: El contrato MUST definir los comandos siguientes; ninguno puede actuar como control en tiempo real:

  | `cmd` | Campos | Efecto | Robot real |
  |---|---|---|---|
  | `start` | — | Inicia corrida con nuevo `run_id` | Sí |
  | `stop` | — | Detiene la corrida y emite `run_finished` | Sí |
  | `set_config` | `controller`, `params`, `base_speed` (todos opcionales; al menos uno) | Cambia la configuración del controlador | Sí |
  | `set_rate` | `hz` (entero 10–100) | Cambia la frecuencia de telemetría | Sí |
  | `list` | — | Responde `catalog` | Sí (ver FR-026) |
  | `reset` | — | Vuelve el robot a la línea de salida | No (solo-sim) |
  | `load` | `robot_id` (string) | Cambia el perfil de robot; el servidor reenvía `hello` y luego `config` (FR-013). Es el único comando que cambia datos de `hello` | No (solo-sim) |
  | `set_profile` | `measured` (objeto parámetro → valor o `null`) | Fija o borra valores medidos de parámetros físicos y de calibración (FR-037) | No (solo-sim) |
  | `load_track` | `track` (pista track v1) | Carga la pista en el mundo | No (solo-sim) |

- **FR-030**: El robot real MUST responder `error` a todo comando solo-sim.
- **FR-031**: `start` con corrida activa MUST responder `error` `run_active` (la corrida en curso continúa sin cambios), y `stop` sin corrida activa MUST responder `error` `no_run` (no se emite `run_finished`).
- **FR-032**: Los comandos solo-sim (`reset`, `load`, `set_profile`, `load_track`) MUST responder `error` `run_active` si hay una corrida activa; se deben enviar con la corrida detenida.
- **FR-033**: `run_id` MUST ser único dentro de la sesión; para identificar una corrida fuera de la sesión se usa el par (`session_id`, `run_id`).
- **FR-034**: `set_config` aceptado durante una corrida MUST aplicarse al instante (al comienzo del siguiente paso de control), emitir un `config` nuevo y marcar la corrida con `config_changed = true` en su `run_finished.summary`. El optimizador MUST descartar las corridas con `config_changed = true`.

#### Perfil del robot

- **FR-035**: Cada parámetro del perfil MUST tener la forma `{"default": valor, "measured": valor | null, "source": origen}`, donde `source` describe el origen del valor por defecto (`defined`, `datasheet`, `estimated`, `current_robot`). El valor efectivo es `measured` si no es `null`; si no, `default`.
- **FR-036**: El perfil v1 MUST contener al menos estos parámetros:

  | Parámetro | Unidad | Defecto v1 | Origen | Campo en `hello` |
  |---|---|---|---|---|
  | `id`, `firmware`, `hw_rev` | — | `velocista-01`, `sim-0.1`, `A` | defined | `robot.id`, `robot.firmware`, `robot.hw_rev` |
  | `line_sensors`, `adc_bits` | — | 16, 12 | current_robot | `capabilities.line_sensors`, `capabilities.adc_bits` |
  | `sensor_pitch_m` | m | 0.009525 | datasheet | — |
  | `sensor_offset_m` (regleta delante del eje) | m | 0.085 | estimated | — |
  | `adc_white`, `adc_black` | ADC | 200, 3900 | estimated | — |
  | `adc_noise` | ADC (±) | 60 | estimated | — |
  | `motors` | — | 2 (fijo en v1) | current_robot | `capabilities.motors` |
  | `max_speed_mps` (a PWM 255) | m/s | 2.8 | estimated | — |
  | `motor_tau_ms` | ms | 45 | estimated | — |
  | `wheelbase_m` | m | 0.130 | estimated | — |
  | `max_lateral_accel_mps2` | m/s² | 9.0 | estimated | — |
  | `turbine` · `turbine_suction_n` | — · N | `false` · `null` | current_robot | `capabilities.turbine` · — |
  | `encoders` · `encoder_ticks_per_rev` | — · ticks | `false` · `null` | current_robot | `capabilities.encoders` · — |
  | `imu` | — | `false` | current_robot | `capabilities.imu` |
  | `battery_cells`, `battery_nominal_v` | —, V | 2, 7.4 | estimated | `capabilities.battery.cells`, `capabilities.battery.nominal_v` |
  | `battery_voltage_sense` | — | `true` | estimated | `capabilities.battery.voltage_sense` |
  | `lap_timing` | — | `true` | defined | `capabilities.lap_timing` |
  | `control_period_ms` | ms | 2 | estimated | — |

  Los parámetros con campo en `hello` son **parámetros de `hello`**; el resto son **parámetros
  físicos y de calibración**.

- **FR-037**: `set_profile` MUST aceptar solo parámetros físicos y de calibración (FR-036): `sensor_pitch_m`, `sensor_offset_m`, `adc_white`, `adc_black`, `adc_noise`, `max_speed_mps`, `motor_tau_ms`, `wheelbase_m`, `max_lateral_accel_mps2`, `turbine_suction_n`, `encoder_ticks_per_rev` y `control_period_ms`. MUST rechazar con `error` `invalid_params` los parámetros de `hello` (`id`, `firmware`, `hw_rev`, `line_sensors`, `adc_bits`, `motors`, `turbine`, `encoders`, `imu`, `lap_timing`, `battery_cells`, `battery_nominal_v`, `battery_voltage_sense`) y los inexistentes, y con `invalid_params` u `out_of_range` los valores con tipo o rango inválido. Se aplica todo o nada. Para cambiar un parámetro de `hello` hay que cargar otro perfil con `load`.

#### Formato de pista (track v1)

- **FR-038**: Una pista track v1 MUST incluir: `id` (string), `v` (entero, `1`), `name` (string), `units` (`"m"`), `board` (`width`, `height`: números > 0, m), `line_width` (número > 0, m), `closed` (booleano), `centerline` (array de ≥ 2 puntos `[x, y]` en m, muestreados cada 0,005 m con una tolerancia de ±10 % entre puntos consecutivos, sin contar el tramo de cierre), `gaps` (array, posiblemente vacío, de `{at, length}` en m), `start` (`{at}` en m) y `rules_profile` (string, perfil de reglamento del trazador, no del robot). Las coordenadas están en metros con origen en la esquina inferior izquierda del tablero, x hacia la derecha e y hacia arriba (el mismo sistema que el trazador); el tablero ocupa `[0, width] × [0, height]`.
- **FR-039**: Todo `at` MUST estar entre 0 y la longitud total de `centerline`; todo punto de `centerline` MUST estar dentro de `board`; los `gaps` MUST NOT superponerse.
- **FR-040**: `marks` (marcas laterales) queda reservado como campo opcional para una versión posterior; en v1 su presencia no invalida la pista pero no tiene efecto.

### Key Entities

- **Sesión**: conexión de un cliente; tiene `session_id`, origen (`sim`/`robot`), perfil, configuración, frecuencia de telemetría y pista activa. Vive mientras la conexión esté abierta.
- **Corrida**: intervalo entre `start` y `stop` o salida de pista; identificada por `run_id` dentro de la sesión. Agrupa telemetría y eventos; termina con un resumen (`run_finished.summary`).
- **Mensaje**: unidad JSON servidor→cliente con envoltorio común (`type`, `v`, `t_ms`).
- **Comando**: unidad JSON cliente→servidor identificada por `cmd`; puede ser general o solo-sim.
- **Capacidades**: lo que el robot declara en `hello` y que determina qué campos opcionales llegan.
- **Perfil del robot**: conjunto de parámetros con valor por defecto, valor medido opcional y origen.
- **Pista (track v1)**: geometría de la línea (centro muestreado, cortes, salida) que solo conoce el mundo simulado.
- **Configuración del controlador**: tipo de controlador, sus parámetros y velocidad base.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de los mensajes y comandos del contrato (6 mensajes, 4 tipos de evento, 9 comandos, perfil y pista) tienen definición validable, ejemplo válido y al menos un ejemplo inválido.
- **SC-002**: La validación automática acepta el 100 % de los ejemplos válidos y rechaza el 100 % de los inválidos, cada uno por el motivo documentado.
- **SC-003**: Los ejemplos del PDF v1.1 (ajustados según las decisiones registradas en *Supuestos*) validan sin errores.
- **SC-004**: Un desarrollador de front, backend u optimizador puede escribir un cliente que procese una sesión completa (conexión, corrida, resumen) usando solo el contrato, sin consultar al equipo del simulador.
- **SC-005**: Cada regla condicionada (`odometry`, `battery_v`, `sim_truth`, `lap`, longitud de `sensors`) tiene al menos un caso que la cumple y uno que la viola.
- **SC-006**: Ninguna pregunta sobre el significado, unidad o rango de un campo queda sin respuesta en el contrato (verificado por revisión de cada integrante de front, backend y firmware).

## Assumptions

- **Envoltorio en eventos**: los ejemplos de `event` del PDF omiten `v`; como el PDF también dice que todo mensaje lleva `v`, se exige `v` en `event`.
- **Comandos**: se identifican por `cmd` (no `type`) como en el PDF; no llevan `t_ms` porque el cliente no conoce el reloj de la sesión.
- **`run_finished.summary.config`**: el PDF lo muestra plano (`kp`, `ki`, `kd` al mismo nivel); se unifica con la forma de `config` (`controller`, `params`, `base_speed`) para que el optimizador pueda reenviarlo directamente como `set_config`.
- **Medición de batería**: el PDF condiciona `battery_v` a que el robot mida voltaje pero `hello` no lo declara; se agrega `capabilities.battery.voltage_sense` (campo nuevo, compatible).
- **Detección de vueltas**: para que `lap` sea opcional sin violar la paridad (constitución, principio II), se agrega `capabilities.lap_timing` (campo nuevo, compatible).
- **`config_changed`**: campo nuevo de `run_finished.summary` (compatible); `summary.config` registra la configuración inicial de la corrida.
- **`code` en `error`**: campo nuevo (compatible) junto a `message`, que el PDF ya tenía.
- **`odometry`**: los campos se condicionan por sensor (encoders → distancia y velocidad; IMU → rumbo), según la sección 8 del PDF.
- **`error` en telemetría**: se define como `line_position` − centro, coherente con el ejemplo (7342 − 7500 = −158).
- **Nombres de parámetros del perfil**: el PDF solo nombra `wheelbase_m`; el resto se nombra en inglés con sufijo de unidad siguiendo la constitución.
- **Controlador**: en v1 solo existe `"pid"`; otros controladores se agregarían en versiones posteriores.
- **Parámetros de conexión desconocidos**: no cierran la conexión; se usa el valor por defecto y se informa con `error`.
- **`run_id`**: string opaco, único por sesión; el backend identifica corridas por (`session_id`, `run_id`).
- **Formato de la definición validable**: JSON Schema por tipo de mensaje en `contract/` (exigido por la constitución, principio VII); la descripción asíncrona completa del canal queda para un spec posterior.
- **Fuera de alcance**: la física del simulador, la implementación del servidor, la interfaz web y la exportación "Para el simulador" del trazador.
- **Dependencias**: el trazador debe exportar track v1 (cambio pendiente fuera de este repo).
