# Interfaz: sesión WebSocket `/ws`

El protocolo es el **contrato v1** (`contract/contract-v1.md`); este documento no agrega ni cambia
mensajes. Fija las decisiones de comportamiento que el contrato deja al servidor.

## Conexión

- URL: `ws://<host>:<port>/ws` local, `wss://<proyecto>.up.railway.app/ws` desplegado.
  Parámetros opcionales `robot` y `track` (IDs del catálogo).
- Secuencia de apertura, siempre con `t_ms = 0`:
  1. `hello` (perfil `robot` o `velocista-01`);
  2. `config` (`controller "pid"`, `kp 0.045`, `ki 0`, `kd 0.9`, `base_speed 180`,
     `rate_hz 50`, `track_id` de `track` o `oval-01`);
  3. si `robot` no existe: `error unknown_robot`; si `track` no existe: `error unknown_track`
     (en ese orden si faltan los dos). La conexión sigue abierta.
- Luego `telemetry` cada `1000/rate_hz` ms de tiempo simulado, siempre.
- Con `VELOCISTA_MAX_SESSIONS` alcanzado, la conexión se acepta y se cierra de inmediato con
  código 1013, sin mensajes.

## Tiempo

- `t_ms` = tiempo simulado de la sesión (pasos × 2 ms). El servidor mantiene tiempo real; si el
  proceso se atrasa más de 100 ms, la simulación se enlentece (no recupera a ráfagas).
- Los comandos recibidos se aplican al inicio del siguiente paso, en orden de llegada; su
  respuesta lleva el `t_ms` de ese paso.

## Comandos

| `cmd` | Condición de aceptación | Efecto | Respuesta | Rechazos |
|---|---|---|---|---|
| `start` | sin corrida | `run_id = "r-<n>"`; robot en `start.at` detenido, PID y motores a 0, ruido con semilla derivada de (semilla base, `n`) | `event run_started` | `run_active` |
| `stop` | con corrida | termina la corrida | `event run_finished` | `no_run` |
| `set_config` | siempre | combina campos; con corrida marca `config_changed` | `config` | `invalid_params`, `out_of_range` |
| `set_rate` | siempre | reinicia el calendario de telemetría | `config` | `invalid_params`, `out_of_range` |
| `list` | siempre | — | `catalog` (`robots` y `tracks` del catálogo + pistas de la sesión) | — |
| `reset` | sin corrida | robot en la salida, detenido | ninguna (se ve en `sim_truth`) | `run_active` |
| `load` | sin corrida | perfil del catálogo sin `measured` previos; conserva config, `rate_hz` y pista; robot a la salida | `hello` + `config` | `run_active`, `unknown_robot`, `invalid_params` |
| `set_profile` | sin corrida | fija/borra `measured`, todo o nada | `config` | `run_active`, `invalid_params`, `out_of_range` |
| `load_track` | sin corrida | pista en el catálogo de la sesión; robot a la salida | `config` (nuevo `track_id`) | `run_active`, `invalid_track`, `invalid_params` |

Precedencia de errores para un frame:

1. No es JSON, contiene `NaN`/`Infinity` o no es objeto → `invalid_json` (sin `cmd`).
2. `v` presente y distinto de `1` → `unsupported_version`.
3. `cmd` ausente, no string o desconocido → `unknown_cmd`.
4. Violaciones del schema (`validate_command`): bajo `/track/…` de `load_track` →
   `invalid_track`; `required`, `type`, `enum`, `const`, `minProperties`, `propertyNames`,
   `not`, `anyOf`, `oneOf` → `invalid_params`; `minimum`, `maximum`, `exclusiveMinimum`,
   `exclusiveMaximum` → `out_of_range`. Con violaciones de ambos grupos gana `invalid_params`.
5. Reglas de estado (`run_active`, `no_run`) y de catálogo (`unknown_robot`).

`error.cmd` va siempre que `cmd` sea un string (incluso si es desconocido); `error.message` en
español, describiendo la primera violación. Un rechazo no cambia nada de la sesión.

## Corridas

- Orden en el paso en que el mundo detecta una salida: `event off_track` → `event run_finished`
  (`off_tracks = 1`) → el `telemetry` de ese paso, si toca, ya con `running = false`.
- `event lap` se emite en el paso en que el progreso alcanza la vuelta; `lap_ms` en ms simulados.
- `summary`: `laps` (vueltas completas), `best_lap_ms`/`avg_lap_ms` (`null` sin vueltas;
  promedio redondeado al ms), `off_tracks`, `track_id`, `config` inicial, `config_changed`.
- Cada corrida tiene ruido distinto: su semilla se deriva de (`VELOCISTA_SEED`, número de corrida
  `n` en la sesión). Misma semilla base, mismo `n`, perfil, pista y config, sin comandos durante
  la corrida → mismo `summary` y misma telemetría de la corrida, sin importar cuándo se envió
  `start`. Repetir la misma config en la corrida siguiente de la sesión da otro ruido y puede dar
  otro `summary`; la secuencia completa de corridas es reproducible en otra sesión.

## Entrega

- `telemetry` puede descartarse si el cliente no lee (más de 25 pendientes): `seq` salta.
- `hello`, `config`, `event`, `error` y `catalog` no se descartan; con más de 1.000 pendientes,
  la conexión se cierra con código 1008.
- Desconexión: la sesión y su corrida se descartan sin `run_finished`.
