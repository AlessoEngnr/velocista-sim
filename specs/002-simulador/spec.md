# Especificación: Simulador de velocista accesible por WebSocket (contrato v1)

**Feature Branch**: `002-simulador`

**Created**: 2026-10-16

**Status**: Draft

**Input**: Descripción del usuario: "Simulador de velocista accesible por WebSocket que cumple el contrato v1 (contract/contract-v1.md). Un servicio desplegado en Railway al que los compañeros se conectan por wss://<url>/ws para recibir datos simulados del velocista mientras el robot real no existe. Prioridad: que el optimizador pueda hacer su ciclo set_config → start → leer run_finished. P1: sesión por conexión con hello y config; mundo con pista por defecto (óvalo track v1) y física simple (regleta de 16 sensores con ruido según el perfil, motores con constante de tiempo, límite de agarre lateral); robot con PID a bordo que solo ve sus sensores; telemetry a rate_hz; eventos run_started, lap, off_track y run_finished con summary; comandos start, stop, set_config, set_rate, list, reset; perfil por defecto velocista-01. P2: load, set_profile y load_track. P3: despliegue en Railway con URL pública, endpoint HTTP de salud y cliente de ejemplo en Python (examples/client.py). Reglas: todo mensaje emitido se valida con velocista_sim.contract en los tests; simulación de paso fijo con semilla, reproducible; mundo y robot son módulos separados. Fuera de alcance: interfaz web, modo batch más rápido que tiempo real, encoders e IMU simulados."

## Contexto

El robot velocista real todavía no existe. Los compañeros que desarrollan el front, el backend y
el optimizador de parámetros necesitan un servicio que se comporte **como el robot** según el
contrato v1 (`contract/contract-v1.md`), para desarrollar y probar contra él desde ya y luego
cambiar al robot real sin modificar sus clientes.

El simulador tiene dos partes que no se mezclan (principio III de la constitución):

- **Mundo**: la pista y la física (posición verdadera del robot, motores, agarre, qué ve cada
  sensor).
- **Robot**: los sensores tal como los lee el robot y el controlador PID a bordo, que solo recibe
  las lecturas de la regleta y su configuración.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - El optimizador corre una configuración y recibe el resumen (Priority: P1)

Un compañero conecta su optimizador al simulador. Al conectarse recibe `hello` y `config`, envía
un `set_config` con los parámetros del PID y la velocidad base, envía `start`, observa la
telemetría y los eventos mientras el robot simulado recorre el óvalo por defecto, y al terminar la
corrida (por `stop` o por salida de pista) recibe `run_finished` con un `summary` que le permite
evaluar la configuración y pasar a la siguiente.

**Why this priority**: es la entrega de mañana. Sin este ciclo el optimizador no puede avanzar, y
cubre por sí solo casi todo el contrato que usan los clientes: sesión, telemetría, eventos y los
comandos generales.

**Independent Test**: conectarse a un simulador local, ejecutar `set_config` → `start` → esperar
`run_finished` (enviando `stop` tras un número de vueltas o al recibir `off_track`) y comprobar
que todos los mensajes recibidos validan contra el contrato y que el `summary` refleja la corrida.

**Acceptance Scenarios**:

1. **Given** un simulador en marcha, **When** un cliente se conecta a `/ws` sin parámetros,
   **Then** recibe primero `hello` (con `source = "sim"`, perfil `velocista-01` y sus capacidades)
   y después `config` (con `controller = "pid"`, los parámetros vigentes, `rate_hz = 50` y
   `track_id` de la pista por defecto), antes de cualquier otro mensaje.
2. **Given** una sesión abierta sin corrida, **When** pasa el tiempo, **Then** el cliente recibe
   `telemetry` a `rate_hz` con `running = false`, sin `run_id` ni bloque `lap`, con `seq`
   creciente de a 1 desde 0, `battery_v` y `sim_truth`.
3. **Given** una sesión sin corrida, **When** el cliente envía `set_config` con un subconjunto de
   campos, **Then** recibe un `config` completo con los campos enviados cambiados y el resto
   intacto.
4. **Given** una sesión sin corrida, **When** el cliente envía `start`, **Then** recibe
   `event run_started` con un `run_id` nuevo y la telemetría pasa a `running = true` con ese
   `run_id` y el bloque `lap`.
5. **Given** una corrida activa con un PID que sigue la línea, **When** el robot completa una
   vuelta, **Then** se emite `event lap` con el número de vuelta y su duración en ms, y
   `telemetry.lap.n` aumenta.
6. **Given** una corrida activa, **When** el cliente envía `stop`, **Then** recibe exactamente un
   `run_finished` con `summary` (vueltas, mejor y promedio de vuelta, salidas de pista, pista,
   configuración con la que empezó y `config_changed`), y la telemetría vuelve a
   `running = false`.
7. **Given** una corrida activa con un PID que no logra seguir la línea, **When** el robot pierde
   la línea de forma definitiva o sale de la pista, **Then** se emite `event off_track` con
   `reason = "line_lost"` seguido inmediatamente de `run_finished` con `off_tracks = 1`.
8. **Given** una corrida activa, **When** el cliente envía `set_config`, **Then** el cambio se
   aplica al comienzo del siguiente paso de control, se emite un `config` nuevo y el `summary`
   final tiene `config_changed = true` y la configuración inicial en `summary.config`.
9. **Given** cualquier momento, **When** el cliente envía `set_rate` con `hz` entre 10 y 100,
   **Then** recibe `config` con el nuevo `rate_hz` y la telemetría pasa a esa frecuencia.
10. **Given** cualquier momento, **When** el cliente envía `list`, **Then** recibe `catalog` con
    los robots y pistas disponibles (al menos `velocista-01` y la pista por defecto).
11. **Given** una sesión sin corrida, **When** el cliente envía `reset`, **Then** el robot vuelve a
    la línea de salida, detenido.
12. **Given** dos clientes conectados a la vez, **When** uno de ellos configura y corre, **Then**
    la sesión del otro no cambia en nada.

---

### User Story 2 - Cambiar de robot, ajustar el perfil y cargar otra pista (Priority: P2)

Un compañero quiere probar el controlador con otro perfil de robot, con valores medidos del robot
físico (p. ej. la distancia entre ruedas real) o en una pista exportada por el trazador. Usa los
comandos solo-sim `load`, `set_profile` y `load_track` con la corrida detenida.

**Why this priority**: aporta realismo y variedad de pistas, pero el ciclo del optimizador ya
funciona con el perfil y la pista por defecto.

**Independent Test**: en una sesión sin corrida, enviar `load_track` con una pista track v1
válida, `set_profile` con un valor medido y `load` con un perfil existente; comprobar las
respuestas (`config`, `hello` + `config`) y que una corrida posterior usa la nueva pista y el
nuevo perfil.

**Acceptance Scenarios**:

1. **Given** una sesión sin corrida, **When** el cliente envía `load` con un `robot_id`
   existente, **Then** recibe un `hello` nuevo seguido de `config`, y todo lo siguiente se emite
   según ese `hello`.
2. **Given** una sesión sin corrida, **When** el cliente envía `load` con un `robot_id`
   inexistente, **Then** recibe `error` `unknown_robot` y la sesión no cambia.
3. **Given** una sesión sin corrida, **When** el cliente envía `set_profile` con valores medidos
   válidos (o `null` para borrarlos), **Then** recibe `config` y la simulación pasa a usar los
   valores efectivos resultantes.
4. **Given** una sesión sin corrida, **When** `set_profile` incluye un parámetro de `hello`, uno
   inexistente, un tipo incorrecto o un valor fuera de rango, **Then** recibe el `error`
   correspondiente (`invalid_params` u `out_of_range`) y no cambia ningún parámetro.
5. **Given** una sesión sin corrida, **When** el cliente envía `load_track` con una pista track
   v1 válida, **Then** recibe `config` con el `track_id` de esa pista y el robot queda en su línea
   de salida.
6. **Given** una sesión sin corrida, **When** `load_track` trae una pista que no cumple track v1,
   **Then** recibe `error` `invalid_track` y la pista vigente no cambia.
7. **Given** una corrida activa, **When** el cliente envía `load`, `set_profile`, `load_track` o
   `reset`, **Then** recibe `error` `run_active` y nada cambia.
8. **Given** un cliente que se conecta con `?robot=<id>&track=<id>` inexistentes, **When** se abre
   la sesión, **Then** recibe `hello` y `config` con los valores por defecto y luego un `error`
   (`unknown_robot` o `unknown_track`), y la conexión sigue abierta.

---

### User Story 3 - Servicio público y cliente de ejemplo (Priority: P3)

Los compañeros se conectan al simulador desplegado en Railway por `wss://<url>/ws` sin instalar
nada. La plataforma comprueba la salud del servicio por HTTP. Un cliente de ejemplo en Python
(`examples/client.py`) muestra cómo conectarse, configurar el PID, correr y mostrar el `summary`.

**Why this priority**: multiplica el valor del simulador para todo el equipo, pero el simulador
ya es útil corriendo localmente.

**Independent Test**: desde una máquina fuera de la red de desarrollo, ejecutar
`examples/client.py` contra la URL pública y ver impreso el `summary` de una corrida; consultar el
endpoint de salud y obtener una respuesta correcta.

**Acceptance Scenarios**:

1. **Given** el servicio desplegado, **When** un compañero se conecta a `wss://<url>/ws`,
   **Then** recibe `hello` y `config` igual que en local.
2. **Given** el servicio desplegado, **When** la plataforma consulta el endpoint HTTP de salud,
   **Then** obtiene una respuesta de éxito mientras el servicio puede aceptar sesiones.
3. **Given** el cliente de ejemplo, **When** se ejecuta con la URL del simulador y unos
   parámetros PID, **Then** se conecta, envía `set_config` y `start`, termina la corrida (con
   `stop` tras un número de vueltas o un tiempo máximo, o por salida de pista) e imprime el
   `summary` de forma legible.

---

### Edge Cases

- **Frame inválido**: un frame que no es JSON o no es un objeto → `error` `invalid_json`; la
  sesión sigue.
- **Comando desconocido o sin `cmd`** → `error` `unknown_cmd`; **`v` distinto de 1** →
  `error` `unsupported_version`; en todos los casos rechazados, la sesión no cambia.
- **Parámetros inválidos**: `set_config` sin ningún campo o con tipos incorrectos →
  `invalid_params`; `set_rate` con `hz = 150` o `base_speed = 300` → `out_of_range`.
- **`start` con corrida activa** → `error` `run_active` y la corrida continúa;
  **`stop` sin corrida** → `error` `no_run` y no se emite `run_finished`.
- **Cortes en la línea (`gaps`)**: cruzar un corte hace que `line_lost` sea `true` brevemente,
  pero **no** debe producir `off_track`; el controlador conserva la última dirección conocida.
- **Robot detenido sin perder la línea** (p. ej. `base_speed = 0`): la corrida sigue hasta que el
  cliente envíe `stop`; nunca termina sola.
- **Curva demasiado rápida**: si la aceleración lateral requerida supera
  `max_lateral_accel_mps2`, el robot derrapa hacia afuera de la curva en lugar de seguir la
  trayectoria pedida; si eso le hace perder la línea, termina en `off_track`.
- **Robot que sale del tablero**: se considera salida de pista (`off_track` con
  `reason = "line_lost"`).
- **Desconexión durante una corrida**: la sesión y la corrida terminan sin `run_finished`; no
  queda estado ni consumo de recursos de esa sesión.
- **Cliente lento**: si el cliente no consume la telemetría a tiempo, el simulador no se atrasa ni
  afecta a otras sesiones; los `telemetry` que no puedan entregarse se pierden (salto en `seq`),
  pero los `event`, `config`, `error` y `catalog` no se descartan.
- **`set_rate` durante una corrida**: se acepta (no es solo-sim) y no altera el resultado de la
  simulación, solo la frecuencia de observación.

## Requirements *(mandatory)*

### Functional Requirements

**Sesión y mensajes (P1)**

- **FR-001**: El sistema MUST aceptar conexiones WebSocket en la ruta `/ws` y crear por cada
  conexión una sesión independiente con un `session_id` único.
- **FR-002**: Al abrirse la sesión, el sistema MUST enviar `hello` y luego `config` antes de
  cualquier otro mensaje.
- **FR-003**: `hello` MUST declarar `source = "sim"`, el perfil cargado (`robot.id`,
  `firmware`, `hw_rev`) y sus capacidades: 16 sensores, ADC de 12 bits, 2 motores, sin turbina,
  sin encoders, sin IMU, `lap_timing = true` y batería con `voltage_sense = true`, tomados del
  perfil efectivo.
- **FR-004**: Todo mensaje emitido MUST llevar el envoltorio común (`type`, `v = 1`, `t_ms`) con
  `t_ms` en ms desde el inicio de la sesión, no decreciente, y un único mensaje JSON por frame.
- **FR-005**: Todo mensaje que emite el sistema MUST validar con `velocista_sim.contract` en el
  contexto del último `hello` de la sesión; los tests MUST comprobarlo para cada tipo de mensaje
  y cada evento.
- **FR-006**: El sistema MUST emitir `telemetry` periódicamente a `rate_hz` (50 Hz por defecto)
  mientras la sesión esté abierta, con o sin corrida, con todos los campos obligatorios y los
  condicionados según `hello` (`battery_v` y `sim_truth` siempre; `run_id` y `lap` solo con
  corrida activa; nunca `odometry`).
- **FR-007**: `telemetry.seq` MUST empezar en 0, aumentar de a 1 por cada `telemetry` generado y
  no reiniciarse nunca en la sesión.
- **FR-008**: Ningún mensaje MUST contener la geometría de la pista, solo su `track_id`.

**Mundo (P1)**

- **FR-009**: El mundo MUST incluir una pista por defecto con forma de óvalo cerrado, definida en
  formato track v1 válido (pasa las reglas del validador de pistas), con `id = "oval-01"`.
- **FR-010**: El mundo MUST modelar el robot como un vehículo de tracción diferencial con
  distancia entre ruedas `wheelbase_m`, cuyos motores responden al PWM con un retardo de primer
  orden de constante `motor_tau_ms`, y cuya velocidad a PWM 255 es `max_speed_mps`.
- **FR-011**: El mundo MUST limitar la aceleración lateral a `max_lateral_accel_mps2`: cuando la
  maniobra pedida la supere, el robot derrapa (su trayectoria real se abre respecto de la pedida).
- **FR-012**: El mundo MUST calcular para cada sensor de la regleta (16 sensores separados
  `sensor_pitch_m`, centrados y a `sensor_offset_m` delante del eje) una lectura ADC que vaya de
  `adc_white` (fuera de la línea o sobre un corte) a `adc_black` (totalmente sobre la línea), con
  valores intermedios según cuánto del sensor cubra la línea, más ruido de amplitud `adc_noise`,
  recortada al rango 0 … 2^`adc_bits` − 1.
- **FR-013**: El mundo MUST detectar las vueltas completadas cuando el robot, en corrida, vuelve
  a cruzar la línea de salida (`start.at`) habiendo recorrido la pista en el sentido de avance.
- **FR-014**: El mundo MUST detectar la salida de pista cuando el robot pierde la línea de forma
  definitiva o sale del tablero, distinguiéndola de la pérdida momentánea al cruzar un corte.
- **FR-015**: El mundo MUST proveer la verdad del robot (`x`, `y`, `theta`, `speed_mps`,
  `distance_m`) solo para el campo `sim_truth` de la telemetría.
- **FR-016**: `battery_v` MUST informar un voltaje plausible derivado de `battery_nominal_v`.

**Robot y controlador (P1)**

- **FR-017**: El robot MUST ejecutar el controlador PID a bordo cada `control_period_ms`,
  recibiendo únicamente las lecturas de la regleta y su configuración (`params`, `base_speed`);
  el módulo del robot MUST NOT importar ni consultar el módulo del mundo.
- **FR-018**: El robot MUST calcular `line_position` (milésimas de sensor, 0 … 15000) a partir de
  las lecturas, `line_lost` (ningún sensor ve la línea) y `error = line_position − 7500`; con la
  línea perdida, MUST conservar la última posición conocida llevada al extremo correspondiente.
- **FR-019**: El robot MUST aplicar a los motores `base_speed ± salida del PID`, recortado a
  −255 … 255, e informar en la telemetría los términos `p`, `i`, `d`, `out` y el PWM aplicado.
- **FR-020**: Sin corrida activa, los motores MUST estar en 0 y el robot quieto; los sensores
  siguen leyéndose y la telemetría refleja sus lecturas.

**Corridas y eventos (P1)**

- **FR-021**: `start` sin corrida activa MUST iniciar una corrida con `run_id` único en la sesión
  y emitir `event run_started`; con corrida activa MUST responder `error` `run_active`.
  Toda corrida aceptada MUST empezar con el robot en la línea de salida, detenido, con los
  motores y el estado del PID reiniciados, sin importar dónde terminó la corrida anterior (el
  equivalente simulado de que alguien coloque el robot real en la salida). Así el ciclo del
  optimizador no necesita `reset`.
- **FR-022**: `stop` con corrida activa MUST terminarla y emitir exactamente un `run_finished`;
  sin corrida MUST responder `error` `no_run`.
- **FR-023**: Al detectarse una salida de pista en corrida, el sistema MUST emitir
  `event off_track` con `reason = "line_lost"` e inmediatamente `run_finished`, y detener la
  corrida.
- **FR-024**: Por cada vuelta completada, el sistema MUST emitir `event lap` con `lap` (número
  de vuelta, desde 1) y `lap_ms`; la telemetría MUST informar `lap.n` (vueltas completadas) y
  `lap.current_ms` (tiempo de la vuelta en curso).
- **FR-025**: `run_finished.summary` MUST incluir `laps`, `best_lap_ms` y `avg_lap_ms` (`null`
  si no hubo vueltas completas), `off_tracks`, `track_id`, la configuración con la que empezó la
  corrida y `config_changed`.
- **FR-026**: Una corrida MUST terminar solo por `stop`, por salida de pista o por cierre de la
  conexión (en este último caso, sin `run_finished`).

**Comandos (P1)**

- **FR-027**: El sistema MUST aceptar `set_config` (parcial, al menos un campo), aplicarlo al
  comienzo del siguiente paso de control y responder `config` completo; aceptado durante una
  corrida, MUST marcarla con `config_changed = true`.
- **FR-028**: El sistema MUST aceptar `set_rate` con `hz` de 10 a 100 y responder `config`.
- **FR-029**: El sistema MUST responder a `list` con `catalog` (robots y pistas disponibles en la
  sesión).
- **FR-030**: El sistema MUST aceptar `reset` sin corrida activa, devolviendo el robot a la línea
  de salida detenido; con corrida activa MUST responder `error` `run_active`.
- **FR-031**: Todo comando rechazado MUST responder `error` con el `code` que indica el contrato
  (y `cmd` cuando sea identificable), con mensaje en español, y no producir ningún efecto.
- **FR-032**: Los comandos MUST aplicarse al inicio de un paso de simulación, nunca a mitad.

**Comandos solo-sim de perfil y pista (P2)**

- **FR-033**: El sistema MUST aceptar `load` con un `robot_id` del catálogo, reenviar `hello` y
  `config` y reinicializar el robot con el nuevo perfil; `robot_id` inexistente → `unknown_robot`.
- **FR-034**: El sistema MUST aceptar `set_profile` según las reglas del contrato (solo los 12
  parámetros físicos y de calibración, todo o nada) y responder `config`; los valores medidos
  MUST prevalecer sobre los por defecto.
- **FR-035**: El sistema MUST aceptar `load_track` con una pista track v1 válida, cargarla en el
  mundo de esa sesión, dejar el robot en su línea de salida y responder `config` con su
  `track_id`; pista inválida → `invalid_track`.
- **FR-036**: `load`, `set_profile`, `load_track` y `reset` con corrida activa MUST responder
  `error` `run_active`.
- **FR-037**: Los parámetros de conexión `robot` y `track` MUST seleccionar el perfil y la pista
  iniciales; si no existen, MUST usarse los por defecto y enviarse `error` `unknown_robot` o
  `unknown_track` tras `hello` y `config`.

**Reproducibilidad y tiempo (todas las prioridades)**

- **FR-038**: La simulación MUST avanzar por pasos fijos de tiempo y no leer el reloj del
  sistema; el servidor solo decide cuándo ejecutar cada paso para mantener el tiempo real.
- **FR-039**: Toda aleatoriedad (ruido de sensores) MUST derivarse de una semilla; con la misma
  semilla, la misma configuración y los mismos comandos en los mismos pasos, el resultado MUST
  ser idéntico.
- **FR-040**: El mundo y el robot MUST ser módulos separados; la información del mundo solo llega
  al robot como lecturas de sensores, y a los clientes solo por `sim_truth`.

**Despliegue y ejemplo (P3)**

- **FR-041**: El servicio MUST poder desplegarse en Railway y quedar accesible por una URL pública
  `wss://<url>/ws`, escuchando en el puerto que asigne la plataforma.
- **FR-042**: El servicio MUST exponer un endpoint HTTP de salud que responda éxito mientras pueda
  aceptar sesiones.
- **FR-043**: El repositorio MUST incluir `examples/client.py`, que recibe la URL y los
  parámetros PID, se conecta, envía `set_config` y `start`, termina la corrida con `stop` tras un
  número de vueltas o un tiempo máximo (o por salida de pista) e imprime el `summary`.

### Key Entities

- **Sesión**: una conexión de cliente; tiene `session_id`, reloj propio (`t_ms`), contador `seq`,
  perfil efectivo, pista vigente, configuración del controlador, `rate_hz`, mundo y robot propios,
  y como máximo una corrida activa.
- **Corrida**: desde `start` hasta `stop` o salida de pista; tiene `run_id`, configuración
  inicial, tiempos de vuelta, contador de salidas de pista y marca `config_changed`.
- **Perfil del robot**: parámetros con valor por defecto y medido (`velocista-01` por defecto);
  el simulador usa siempre el valor efectivo.
- **Pista**: en formato track v1 (línea central, cortes, línea de salida, tablero); la conoce solo
  el mundo.
- **Mundo**: estado verdadero (pose, velocidades de ruedas, distancia recorrida, avance sobre la
  pista) y física; produce lecturas de sensores y detecta vueltas y salidas de pista.
- **Robot (a bordo)**: lee la regleta, calcula `line_position`, ejecuta el PID y decide el PWM de
  cada motor.
- **Catálogo**: robots y pistas disponibles para la sesión.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Con la configuración PID por defecto, un cliente completa el ciclo
  `set_config` → `start` → `run_finished` en el óvalo por defecto y el robot da al menos 3
  vueltas sin salirse antes de enviar `stop`.
- **SC-002**: El 100 % de los mensajes emitidos en los tests (todos los tipos y eventos, en todos
  los escenarios de aceptación) valida contra el contrato v1.
- **SC-003**: Dos ejecuciones con la misma semilla, configuración y secuencia de comandos producen
  `summary` y telemetría idénticos (salvo `session_id`).
- **SC-004**: La telemetría llega a la frecuencia configurada con un desvío promedio menor al 5 %
  medido durante 10 s, con hasta 5 sesiones simultáneas.
- **SC-005**: Una configuración PID claramente mala (p. ej. `kp = 0`) termina en `off_track` y
  `run_finished` en menos de 10 s de corrida, y cruzar los cortes de una pista con un PID bueno no
  produce `off_track`.
- **SC-006**: Un compañero sin el repositorio instalado se conecta a la URL pública y obtiene el
  `summary` de una corrida con el cliente de ejemplo en menos de 5 minutos desde que recibe las
  instrucciones.
- **SC-007**: Ningún comando rechazado en los tests cambia el estado de la sesión (comprobado
  comparando la configuración y la telemetría antes y después).

## Assumptions

- La pista por defecto `oval-01` es un óvalo cerrado sin cortes que entra en un tablero de unos
  3 × 2,5 m, con ancho de línea de 0,019 m; su línea de salida está sobre una recta.
- `off_track` se informa siempre con `reason = "line_lost"` (único valor de v1), tanto si el robot
  pierde la línea de forma definitiva como si sale del tablero. "Pérdida definitiva" significa que
  la línea sigue sin verse tras recorrer una distancia mayor que cualquier corte razonable (del
  orden de 0,1 m) o que el robot se aleja de la línea más que el ancho de la regleta; los valores
  exactos se fijan en el plan.
- La semilla es fija y configurable del lado del servidor (no la elige el cliente, porque el
  contrato v1 no define un parámetro para ello); todas las sesiones con la misma semilla son
  reproducibles entre sí.
- Los parámetros PID por defecto del `config` inicial son razonables para seguir el óvalo a
  velocidad moderada (se ajustan en el plan); `base_speed` por defecto moderado.
- `battery_v` se modela como el voltaje nominal (con una caída leve opcional); no hay modelo de
  descarga realista.
- La velocidad de las ruedas es proporcional al PWM (a voltaje nominal), sin zona muerta ni
  saturación adicional en v1.
- El catálogo inicial tiene un solo robot (`velocista-01`) y una sola pista (`oval-01`); las pistas
  cargadas con `load_track` quedan disponibles solo dentro de la sesión que las cargó.
- La P2 (`load`, `set_profile`, `load_track`) se implementa antes del despliegue (P3); no hay
  respuesta provisional para esos comandos que se aparte del contrato.
- La terminación de corridas sin salida de pista es responsabilidad del cliente (envía `stop`),
  como define el contrato; el optimizador y el cliente de ejemplo lo hacen tras N vueltas o un
  tiempo máximo.
- El número de sesiones simultáneas esperado es bajo (el equipo del curso, del orden de 5 a 10).
- No hay autenticación: el servicio es público para el equipo durante el desarrollo.
- Fuera de alcance: interfaz web, modo batch más rápido que tiempo real, encoders e IMU simulados
  (`odometry` nunca se emite), turbina.
