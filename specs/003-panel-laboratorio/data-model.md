# Data model: Panel de laboratorio web

**Feature**: `003-panel-laboratorio` · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md)

Todo el estado vive **en memoria del navegador**, en un objeto `state` por pestaña
(`static/js/state.js`). No hay persistencia (FR-036) ni estado nuevo en el servidor. Los nombres
de campos del contrato se usan tal cual; los identificadores propios del panel van en inglés
(constitución, flujo de desarrollo).

## Vista general

```text
PanelState
├── connection: Connection
├── hello: Hello | null            ← último `hello` (contrato)
├── config: Config | null          ← último `config` (contrato)
├── catalog: Catalog | null        ← último `catalog` (contrato)
├── pending: PendingCommand[]      ← cola FIFO (research R5)
├── telemetry: TelemetryView       ← última telemetría + contadores
├── run: ObservedRun | null        ← corrida activa
├── trail: Trail                   ← rastro de `sim_truth`
├── lapTarget: LapTarget
├── calibration: Calibration
├── summaries: RunSummary[]        ← máx. 50, la más reciente primero
├── log: LogEntry[]                ← máx. 50, el más reciente primero
└── drafts: ControlDrafts          ← valores en edición de los controles
```

## Entidades

### Connection

| Campo | Tipo | Regla |
|---|---|---|
| `status` | `"connecting" \| "open" \| "closed"` | ver transiciones |
| `url` | string | `ws(s)://<host>/ws` + `?track=&robot=` solo al cambiar de pista (R4) |
| `closeCode` | entero \| null | código del último cierre (1013 → servidor lleno; 1008 → cliente lento) |
| `sessionId` | string \| null | `hello.session_id` |

```text
           new WebSocket            onopen               onclose / onerror
 (inicio) ───────────────► connecting ──────► open ─────────────────────► closed
                              │                                              │
                              └──────────── onclose (rechazo, 1013) ────────►│
 closed ── Reconectar / cambiar pista ──► connecting   (se reinicia todo menos `log`)
```

Los comandos solo se envían con `status = "open"`; con otro estado los controles están
deshabilitados (borde "comandos con la conexión cerrada").

### Hello (contrato) y capacidades derivadas

Copia del último `hello`. De él se derivan banderas que rigen la UI (FR-006, FR-035):

| Derivado | Fórmula | Efecto |
|---|---|---|
| `isSim` | `source === "sim"` | muestra Reiniciar, Robot y pista, Calibración, Rastro |
| `sensorCount` | `capabilities.line_sensors` | barras de la regleta |
| `adcMax` | `2 ** capabilities.adc_bits − 1` | escala de la regleta |
| `hasBattery` | `capabilities.battery.voltage_sense` | muestra `battery_v` |
| `hasLaps` | `capabilities.lap_timing` | muestra vueltas y vueltas objetivo |

Un `hello` nuevo en la misma sesión (tras `load`): reemplaza al anterior, rearma las vistas,
limpia el rastro y reinicia `calibration` a "por defecto".

### Config (contrato)

Último `config` confirmado: `controller`, `params.kp/ki/kd`, `base_speed`, `rate_hz`,
`track_id`. Es la **fuente de verdad** de los controles (FR-013): al llegar, los controles que no
se están arrastrando toman estos valores; ante un `error` de `set_config`/`set_rate`, todos
vuelven a ellos.

### Catalog (contrato)

`robots: string[]`, `tracks: string[]`. Se pide con `list` al abrirse cada sesión (después del
primer `config`) y con el botón Actualizar. El robot vigente es `hello.robot.id`; la pista
vigente, `config.track_id`.

### PendingCommand (research R5)

| Campo | Tipo | Regla |
|---|---|---|
| `cmd` | `"set_config" \| "set_rate" \| "set_profile" \| "load_track" \| "load"` | solo estos entran en la cola |
| `payload` | objeto | el comando enviado (para `set_profile`: los `measured` enviados) |

- Entran a la cola solo los comandos que responden con `config`. `start`, `stop`, `list` y
  `reset` **no entran** (`reset` sin corrida no responde nada).
- Se encola al enviar.
- `config` recibido → resuelve como **aceptado** el pendiente más antiguo de la cola (para
  `load`, el `hello` previo se aplica y el `config` lo resuelve).
- `error` con `cmd` → resuelve como **rechazado** el pendiente más antiguo cuyo `cmd` coincida
  con `error.cmd`; si ninguno coincide, la cola no cambia.
- `error` sin `cmd` → no toca la cola.
- Al cerrarse la conexión, la cola se vacía.

### TelemetryView

| Campo | Tipo | Regla |
|---|---|---|
| `last` | telemetría del contrato \| null | la última recibida; la que se dibuja |
| `lastSeq` | entero \| null | `seq` de la última |
| `lost` | entero ≥ 0 | suma de `seq − lastSeq − 1` cuando es > 0 (FR-019) |
| `received` | entero ≥ 0 | telemetrías recibidas en la sesión |

`lastSeq` y `lost` se reinician con cada sesión nueva (el `seq` es por sesión).

### ObservedRun

Desde `event run_started` hasta `event run_finished`.

| Campo | Tipo | Regla |
|---|---|---|
| `runId` | string | `event.run_id` |
| `laps` | `{n, lapMs}[]` | de cada `event lap`; máx. 100, la más reciente primero |
| `bestLapMs`, `lastLapMs`, `avgLapMs` | entero \| null | calculados por el panel de `laps` mientras corre; al terminar se muestran los de `summary` |
| `offTracks` | `{tMs, reason}[]` | de cada `event off_track` |

```text
            event run_started (o telemetry.running=true con run_id nuevo)
 sin corrida ───────────────────────────────────────────────► en corrida
     ▲                                                             │
     └──────────── event run_finished ◄── (stop | off_track) ──────┘
```

- Al enviar `start`: se limpia el rastro. Al entrar en "en corrida": se limpia `laps`.
- Si llega `telemetry.running = false` sin `run_finished` (no debería pasar), el panel vuelve a
  "sin corrida" sin agregar resumen.
- Iniciar se habilita solo en "sin corrida"; Detener solo en "en corrida".

### RunSummary

El `summary` de `run_finished` tal cual (contrato) más el `run_id` y el `t_ms` del evento:
`laps`, `best_lap_ms`, `avg_lap_ms`, `off_tracks`, `track_id`, `config` (`controller`, `params`,
`base_speed`), `config_changed`. Se antepone a `summaries` (tope 50). Los `null` se muestran como
`—` (FR-022).

### Trail (research R7)

| Campo | Tipo | Regla |
|---|---|---|
| `xs`, `ys` | `Float32Array(5000)` | buffer circular de posiciones (m) |
| `start`, `length` | entero | índice del más antiguo y cantidad guardada |
| `bounds` | `{minX, maxX, minY, maxY}` | caja de los puntos guardados; se recalcula al sobrescribir |
| `pose` | `{x, y, theta}` \| null | último `sim_truth` |

- Se agrega un punto por cada telemetría con `sim_truth` (no solo por cada cuadro dibujado).
- Se limpia en **cada `start`** enviado, al enviar `reset`, con `load` o `load_track` aceptados,
  al abrir una sesión nueva y a mano con el botón **Limpiar rastro** (acción local, no envía
  nada).
- Solo existe con `isSim`.

### LapTarget (research R16)

| Campo | Tipo | Regla |
|---|---|---|
| `value` | entero ≥ 1 \| null | `null` = sin límite |
| `stopSentFor` | string \| null | `run_id` al que ya se le envió el `stop` automático |

Un valor inválido en el campo no cambia `value` y marca el campo con `aria-invalid="true"`.

### Calibration

Un registro por cada uno de los 12 parámetros de `set_profile` (metadatos fijos en
`profile-params.js`):

| Campo | Tipo | Regla |
|---|---|---|
| `key` | string | nombre del contrato, p. ej. `wheelbase_m` |
| `label` | string | nombre en español, p. ej. "Distancia entre ruedas" |
| `unit` | string | `m`, `ADC`, `m/s`, `ms`, `m/s²`, `N`, `ticks` |
| `range` | texto + validador | según la tabla del contrato (p. ej. `> 0`, `0–65535`, `≥ 1`) |
| `integer` | booleano | `adc_white`, `adc_black`, `adc_noise`, `encoder_ticks_per_rev` |
| `measured` | número \| null | valor aceptado en esta sesión; `null` = "por defecto" |
| `draft` | string | lo que el usuario escribió y aún no aplicó |

Tabla fija (FR-029):

| `key` | Rótulo | Unidad | Rango | Entero |
|---|---|---|---|---|
| `sensor_pitch_m` | Separación entre sensores | m | > 0 | no |
| `sensor_offset_m` | Distancia de la regleta al eje | m | > 0 | no |
| `adc_white` | Lectura sobre blanco | ADC | 0–65535 | sí |
| `adc_black` | Lectura sobre negro | ADC | 0–65535 | sí |
| `adc_noise` | Ruido de la regleta | ADC (±) | ≥ 0 | sí |
| `max_speed_mps` | Velocidad máxima (PWM 255) | m/s | > 0 | no |
| `motor_tau_ms` | Constante de tiempo del motor | ms | > 0 | no |
| `wheelbase_m` | Distancia entre ruedas | m | > 0 | no |
| `max_lateral_accel_mps2` | Agarre lateral máximo | m/s² | > 0 | no |
| `turbine_suction_n` | Succión de la turbina | N | ≥ 0 | no |
| `encoder_ticks_per_rev` | Pulsos del encoder por vuelta | ticks | ≥ 1 | sí |
| `control_period_ms` | Período de control | ms | > 0 | no |

Validación local antes de enviar (FR-030): que el texto sea un número finito (y entero donde
corresponde). El **rango** lo decide el servidor (`out_of_range`), para no duplicar reglas del
contrato; el rango se muestra como ayuda.

Transiciones: aplicar → `PendingCommand set_profile` → aceptado: `measured = valor` (o `null` al
borrar) en los parámetros enviados; rechazado: sin cambios. `hello` nuevo o sesión nueva: todos
`measured = null`.

### LogEntry

| Campo | Tipo | Regla |
|---|---|---|
| `kind` | `"event" \| "error" \| "local" \| "warning"` | `warning`: mensaje no interpretable o `type` desconocido |
| `tMs` | entero \| null | `t_ms` del mensaje; `null` para locales (se muestra la hora de la sesión del último mensaje) |
| `text` | string | p. ej. `lap 3 · 12.634 s`, `out_of_range · set_rate · <message>` |
| `code`, `cmd` | string \| null | del `error`; un `code` desconocido se muestra como error genérico |

Tope 50, el más reciente primero. Se conserva entre reconexiones (incluye el aviso de
desconexión) y se pierde al recargar.

### ControlDrafts

Valor en edición de `kp`, `ki`, `kd`, `base_speed`, `rate_hz`, y si el usuario está arrastrando
ese control. Mientras arrastra, un `config` entrante no le "roba" el slider; al soltar, el
control muestra el valor confirmado del siguiente `config`.

## Reglas de interpretación (resumen de `applyMessage`)

| `type` | Efecto |
|---|---|
| `hello` | reemplaza `hello`, recalcula derivados, limpia rastro y calibración (el `load` pendiente lo resuelve el `config` siguiente) |
| `config` | reemplaza `config`; resuelve como aceptado el pendiente más antiguo; si era `load_track`, limpia el rastro |
| `telemetry` | `TelemetryView`, punto del rastro, estado de corrida, vuelta en curso, vueltas objetivo |
| `event` | `run_started` / `lap` / `off_track` / `run_finished` → `ObservedRun`, `summaries`, `log`, vueltas objetivo |
| `catalog` | reemplaza `catalog` |
| `error` | `log`; resuelve como rechazado el pendiente más antiguo con el mismo `cmd` (si hay); reponer controles |
| otro / JSON inválido | se ignora y se registra como `warning` |
