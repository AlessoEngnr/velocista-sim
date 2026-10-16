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

<!-- Se completa con la historia de usuario 1. -->

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
