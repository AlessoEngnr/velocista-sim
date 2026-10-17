# Contrato de uso del protocolo: el panel como cliente v1

Describe **qué** mensajes del contrato v1 (`contract/contract-v1.md`) usa el panel y **cuándo**.
No agrega nada al contrato: es su uso por un cliente (FR-003). Sirve de guía para el front del
equipo (SC-007).

## Conexión

```js
// static/js/connection.js
const scheme = location.protocol === "https:" ? "wss:" : "ws:";
const url = new URL("/ws", `${scheme}//${location.host}`);
// Solo al cambiar de pista del catálogo (FR-026):
url.searchParams.set("track", trackId);
url.searchParams.set("robot", currentRobotId);
```

- Un frame de texto = un comando JSON. Los comandos **no** llevan `v` (es opcional) ni `t_ms`.
- Al abrirse: espera `hello` y luego `config`; tras el primer `config` envía `list`.
- Cierre con 1013 → "servidor lleno"; con 1008 → "el panel no leía a tiempo"; cualquier otro →
  "desconectado". Sin reconexión automática (research R15).

## Comandos que envía (`static/js/commands.js`)

Cada función devuelve el objeto a enviar; no tiene efectos. Es la **única** forma de construir
comandos en el panel, y todos se validan con `validate_command` en los tests (FR-037).

| Función | Comando producido | Cuándo lo envía el panel | Se habilita si |
|---|---|---|---|
| `start()` | `{"cmd":"start"}` | botón Iniciar (limpia el rastro al enviarlo) | `open`, sin corrida |
| `stop()` | `{"cmd":"stop"}` | botón Detener; vueltas objetivo alcanzadas (una vez por `run_id`) | `open`, en corrida |
| `reset()` | `{"cmd":"reset"}` | botón Reiniciar | `open`, sin corrida, `isSim` |
| `setConfig({kp})` … | `{"cmd":"set_config","params":{"kp":0.05}}` | slider/campo de `kp`, `ki` o `kd` (throttle 200 ms) | `open` |
| `setConfig({base_speed})` | `{"cmd":"set_config","base_speed":180}` | slider/campo de `base_speed` | `open` |
| `setRate(hz)` | `{"cmd":"set_rate","hz":20}` | campo de frecuencia (10–100) | `open` |
| `list()` | `{"cmd":"list"}` | al abrir sesión; botón Actualizar catálogo | `open` |
| `load(robotId)` | `{"cmd":"load","robot_id":"velocista-01"}` | elegir robot | `open`, sin corrida, `isSim` |
| `setProfile(measured)` | `{"cmd":"set_profile","measured":{"wheelbase_m":0.128,"adc_noise":null}}` | Aplicar / Borrar en Calibración | `open`, sin corrida, `isSim` |
| `loadTrack(track)` | `{"cmd":"load_track","track":{…}}` | elegir archivo JSON válido | `open`, sin corrida, `isSim` |

Reglas:

- `set_config` lleva solo el campo cambiado; `base_speed` se redondea a entero y se limita a
  0–255; `kp`, `ki`, `kd` deben ser ≥ 0 (si no, el campo se marca inválido y no se envía).
- `set_profile` envía en un único comando todos los borradores válidos; los enteros del contrato
  se envían como enteros.
- `load_track` envía el contenido del archivo tal cual tras `JSON.parse`; si el parseo falla,
  error local y nada se envía. La validez track v1 la decide el servidor (`invalid_track`).
- Cambiar de pista del catálogo **no** es un comando: es una reconexión (ver Conexión), previa
  confirmación del usuario.

## Mensajes que procesa (`static/js/state.js`, `applyMessage`)

| `type` | Uso en el panel |
|---|---|
| `hello` | datos del robot y capacidades; rige qué se muestra (FR-005, FR-006) |
| `config` | valores confirmados de los controles; `track_id` vigente (FR-013) |
| `telemetry` | regleta, línea, PID, motores, batería, vuelta en curso, rastro (`sim_truth`), `seq` |
| `event` | `run_started`, `lap`, `off_track`, `run_finished` → corrida, vueltas, resúmenes, registro |
| `catalog` | listas de robots y pistas |
| `error` | registro visible; rechaza el pendiente más antiguo cuyo `cmd` coincida con `error.cmd` |

- Campos desconocidos: se ignoran (contrato, Versionado).
- `type` desconocido o frame no JSON: se ignora y se registra como aviso.
- `code` de error desconocido: se muestra como error genérico con su `message`.
- Elementos solo-sim (`sim_truth`, `reset`, `load`, `set_profile`, `load_track`): con
  `source = "robot"` las vistas y controles correspondientes se ocultan; el resto del panel
  funciona igual (FR-035, principio II).

## Correlación de respuestas

Cola FIFO de pendientes solo con los comandos que responden con `config`: `set_config`,
`set_rate`, `set_profile`, `load` y `load_track`.

- Un `config` resuelve como aceptado el pendiente **más antiguo** de la cola.
- Un `error` resuelve como rechazado el pendiente más antiguo cuyo `cmd` coincida con
  `error.cmd`; si no hay ninguno, la cola no cambia.
- `start`, `stop`, `list` y `reset` **no entran** a la cola (`reset` sin corrida no responde
  nada); sus `error` solo se muestran en el registro.

Detalle en [../research.md](../research.md) R5 y [../data-model.md](../data-model.md).
