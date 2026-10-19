# Especificación: Panel de laboratorio web para el simulador

**Feature Branch**: `003-panel-laboratorio`

**Created**: 2026-10-16

**Status**: Draft

**Input**: Descripción del usuario: "Panel de laboratorio web para el simulador, servido por el mismo servicio en la ruta /. Qué: una página que se conecta a /ws del mismo servidor y permite ver y ajustar la simulación en vivo, usando solo mensajes del contrato v1 (es un cliente más, y sirve de ejemplo para el front del equipo). Funciones: estado de conexión y datos del hello (robot, capacidades); control: start, stop, reset; sliders de kp, ki, kd y base_speed (set_config); frecuencia de telemetría (set_rate); robot y pista: elegir robot y pista del catálogo (list, load); cargar una pista desde un archivo JSON (load_track); calibración: editar los valores medidos del perfil (ruido, velocidad máxima, agarre, etc.) con set_profile, y poder borrarlos; visualización en vivo: barra de los 16 sensores, line_position y error, términos del PID, PWM de cada motor, batería, y el rastro del robot dibujado a partir de sim_truth; historial de vueltas y resúmenes de corridas; errores visibles en pantalla. Fuera de alcance: armar robots nuevos, dibujar la geometría de la pista (no viaja por el contrato), cuentas de usuario y guardar datos."

## Contexto

El simulador (feature `002-simulador`) ya acepta sesiones por `/ws` según el contrato v1
(`contract/contract-v1.md`), pero hoy solo se usa desde scripts (el optimizador y
`examples/client.py`). Para ajustar un PID, calibrar el perfil o entender por qué el robot se sale
de la pista, el equipo necesita **ver** la simulación en vivo y tocar parámetros sin escribir
código.

El panel es una página web que el mismo servicio entrega en la ruta `/`. Para el simulador es **un
cliente más**: abre su propia sesión en `/ws` y solo usa mensajes y comandos del contrato v1, sin
canales ni datos extra. Por eso también sirve de ejemplo de referencia para el front del equipo,
que tendrá que funcionar igual contra el robot real.

## Referencia visual

Diseño de referencia: [`docs/design/reference.png`](../../docs/design/reference.png), un tablero
oscuro tipo "Mission Control" de carreras. **Solo se toman sus rasgos de identidad**: paleta,
tipografía, acentos de marca y la organización en tarjetas sobre una grilla de tres columnas. El
panel NO es un tablero visual ni de espectáculo: es **instrumentación de laboratorio**, sobria,
técnica y densa en datos, pensada para leer valores rápido mientras se ajusta el controlador.

### Qué se conserva del diseño

| Rasgo del diseño | Cómo se aplica en el panel |
|---|---|
| Fondo casi negro, tarjetas apenas más claras con bordes sutiles y esquinas levemente redondeadas | Igual: fondo oscuro, una tarjeta por grupo de datos, sin sombras marcadas |
| Acento de marca magenta/carmesí | Único color de marca: identidad (logo, título), elemento activo o seleccionado y el rastro del robot |
| Punto "LIVE" junto a títulos | Indicador de estado: conexión abierta y corrida activa (sin parpadeo) |
| Etiquetas pequeñas en mayúsculas, gris tenue, con espaciado de letras | Igual para todos los rótulos de valores (p. ej. `ERROR`, `LINE POS`, `BATERÍA`) |
| Valores grandes en blanco debajo de su etiqueta | Igual, pero en **fuente monoespaciada** de cifras tabulares, con su unidad |
| Segundo acento azul claro para el mejor tiempo | Mismo uso: resaltar la mejor vuelta |
| Barra superior con métricas clave en línea | Barra superior de estado de la sesión y de la corrida (ver Distribución) |
| Control segmentado pequeño (`All` / `TOP 5` / `TOP 10`) | Mismo estilo para alternar pestañas o vistas dentro de una tarjeta |
| Tipografía sans-serif geométrica para textos | Igual para rótulos y textos; los números siempre en monoespaciada |

### Qué se descarta por estilo (no es instrumentación)

Fotografías y retratos, video y cámaras, mapa satelital de fondo, brillo/resplandor del trazado,
degradados, iconografía decorativa, barra lateral de íconos de navegación, forma de onda de audio y
cualquier animación que no sea la actualización de los propios valores.

### Elementos del diseño que el contrato v1 no permite (fuera de alcance)

| Elemento del diseño | Motivo | Sustituto en el panel |
|---|---|---|
| Clima (aire, temperatura de pista, humedad, viento) | No existe en el contrato | — |
| Posición en carrera, gap al líder, "Battle for position", tabla de posiciones, filtros Top 5/10 | Una sesión tiene un solo robot; no hay rivales | — |
| Cámara en vivo / onboard | El contrato no transmite video | — |
| Team Radio (comunicaciones de voz/texto) | No existe en el contrato | Tarjeta **Registro**: eventos (`run_started`, `lap`, `off_track`, `run_finished`) y `error`, con `t_ms` |
| Mapa de la pista con su trazado, sectores S1/S2/S3 y tiempos por sector | La geometría de la pista no viaja por el contrato (FR-021 del contrato) y no hay sectores | Tarjeta **Rastro**: trayectoria de `sim_truth` sin pista de fondo |
| Total de vueltas de la carrera (`42 / 78`) | El contrato no define una cantidad de vueltas objetivo; la corrida termina con `stop` o salida de pista | `lap.n / vueltas objetivo`, un campo opcional del panel que envía `stop` al alcanzarlo (FR-045) |
| Velocidad en km/h, acelerador, freno, RPM | No existen en el contrato | `sim_truth.speed_mps` (m/s) y PWM de cada motor |
| Foto, número y equipo del piloto | No existen en el contrato | Datos del robot de `hello` (`robot.id`, `firmware`, `hw_rev`) |
| Botones de ajustes de cuenta, auriculares y cerrar sesión | No hay cuentas ni audio | — |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver la simulación en vivo y controlar corridas (Priority: P1)

Un compañero abre la URL del simulador en el navegador. El panel se conecta solo, muestra que la
conexión está abierta y los datos del robot (`hello`: id, firmware, revisión, `source` y
capacidades) y la configuración vigente (`config`). Pulsa **Iniciar**, ve la regleta de sensores,
la posición de la línea, el error, los términos del PID, el PWM de cada motor, la batería y el
rastro del robot dibujándose mientras recorre la pista; ve las vueltas a medida que se completan y,
al pulsar **Detener** o al salirse el robot, el resumen de la corrida.

**Why this priority**: es el núcleo del panel: sin ver la telemetría y controlar corridas no hay
laboratorio. Por sí solo ya permite observar el comportamiento del PID por defecto y es el ejemplo
mínimo de cliente para el front.

**Independent Test**: con el simulador corriendo en local, abrir `/` en un navegador, comprobar el
estado de conexión y los datos de `hello` y `config`, pulsar Iniciar, ver la visualización
actualizándose y al menos una vuelta en el historial, pulsar Detener y ver el resumen.

**Acceptance Scenarios**:

1. **Given** el simulador en marcha, **When** el usuario abre `/` en el navegador, **Then** el
   panel se conecta a `/ws` del mismo servidor (con `wss` si la página llegó por `https`) y muestra
   el estado "conectado", el `session_id`, el robot (`id`, `firmware`, `hw_rev`), `source` y las
   capacidades de `hello`, y la configuración de `config` (controlador, `kp`, `ki`, `kd`,
   `base_speed`, `rate_hz`, `track_id`).
2. **Given** una sesión abierta sin corrida, **When** llega telemetría, **Then** el panel muestra
   la lectura de cada sensor de la regleta (tantos como `capabilities.line_sensors`), la
   `line_position`, el `error`, si la línea está perdida, los términos `p`, `i`, `d` y `out`, el
   PWM de los motores izquierdo y derecho, la batería y el estado "sin corrida".
3. **Given** una sesión sin corrida, **When** el usuario pulsa Iniciar, **Then** el panel envía
   `start`, al recibir `event run_started` muestra el `run_id` y el estado "en corrida", limpia el
   rastro anterior y empieza a dibujar el nuevo a partir de `sim_truth.x` y `sim_truth.y`.
4. **Given** una corrida activa, **When** llega `event lap`, **Then** el historial de vueltas de
   esa corrida agrega el número de vuelta y su duración, y se ve la vuelta en curso con su tiempo
   (`telemetry.lap`).
5. **Given** una corrida activa, **When** el usuario pulsa Detener, **Then** el panel envía `stop`
   y, al recibir `run_finished`, agrega el resumen (vueltas, mejor y promedio de vuelta, salidas de
   pista, pista, configuración inicial y si cambió durante la corrida) a la lista de resúmenes de
   la sesión, y vuelve al estado "sin corrida".
6. **Given** una corrida activa, **When** el robot se sale de la pista, **Then** el panel señala la
   salida de pista (`event off_track` con su `reason`) y muestra el resumen del `run_finished` que
   le sigue.
7. **Given** el campo de vueltas objetivo en 3, **When** la corrida completa la tercera vuelta,
   **Then** el panel envía `stop` una sola vez y muestra el resumen; **Given** el mismo objetivo,
   **When** el usuario pulsa Detener en la vuelta 1, **Then** la corrida termina ahí; **Given** el
   campo vacío, **When** pasan las vueltas, **Then** el panel nunca envía `stop` por su cuenta.
8. **Given** una sesión sin corrida, **When** el usuario pulsa Reiniciar, **Then** el panel envía
   `reset` y el rastro se limpia; el robot vuelve a la salida.
9. **Given** cualquier momento, **When** el servidor responde `error`, **Then** el panel lo muestra
   en pantalla con su `code`, su `message` y el `cmd` rechazado, sin perder el resto del estado.
10. **Given** una sesión abierta, **When** se corta la conexión, **Then** el panel muestra el estado
   "desconectado", deja de habilitar los comandos y ofrece reconectar; al reconectar trata la
   nueva sesión como nueva (nuevo `hello`, nuevo `config`, rastro limpio).

---

### User Story 2 - Ajustar el controlador en vivo (Priority: P1)

El compañero mueve los controles de `kp`, `ki`, `kd` y `base_speed` y ve el efecto en el
comportamiento del robot, antes o durante una corrida. También cambia la frecuencia de telemetría
para observar con más o menos detalle.

**Why this priority**: ajustar el PID viendo el resultado es la razón principal del laboratorio;
comparte prioridad con la visualización porque una sin la otra vale poco.

**Independent Test**: con una sesión abierta, mover cada control y comprobar que se envía
`set_config` (o `set_rate`) con el valor elegido, que el panel muestra el `config` de respuesta y
que, durante una corrida, el resumen final indica que la configuración cambió.

**Acceptance Scenarios**:

1. **Given** una sesión abierta, **When** llega `config`, **Then** los controles de `kp`, `ki`,
   `kd`, `base_speed` y frecuencia se ubican en los valores vigentes informados.
2. **Given** una sesión abierta, **When** el usuario cambia `kp`, `ki`, `kd` o `base_speed`,
   **Then** el panel envía `set_config` con el campo cambiado y, al recibir `config`, muestra los
   valores confirmados por el servidor.
3. **Given** el usuario arrastra un control de forma continua, **When** el valor cambia muchas
   veces seguidas, **Then** el panel no envía un comando por cada paso intermedio: envía como
   máximo unos pocos por segundo y siempre el valor final.
4. **Given** el usuario necesita un valor preciso, **When** lo escribe en el campo numérico junto
   al control, **Then** se envía ese valor exacto, aunque esté fuera del recorrido del control
   deslizante (siempre que sea ≥ 0 para `kp`, `ki`, `kd`).
5. **Given** una sesión abierta, **When** el usuario elige otra frecuencia de telemetría entre 10
   y 100 Hz, **Then** el panel envía `set_rate` y, tras el `config` de respuesta, la telemetría
   llega a la nueva frecuencia.
6. **Given** el servidor rechaza un valor (p. ej. `out_of_range`), **When** llega el `error`,
   **Then** el panel lo muestra y los controles vuelven al último valor confirmado por `config`.

---

### User Story 3 - Elegir robot y pista, cargar pistas desde archivo (Priority: P2)

El compañero quiere probar otro perfil de robot o una pista exportada por el trazador. Desde el
panel pide el catálogo, elige un robot o una pista, o selecciona un archivo JSON de pista en su
equipo para cargarlo.

**Why this priority**: amplía las pruebas a otros robots y pistas, pero el laboratorio ya es útil
con el robot y la pista por defecto.

**Independent Test**: con una sesión sin corrida, pedir el catálogo, cargar un robot con `load` y
comprobar que el panel actualiza los datos de `hello`; cargar un archivo de pista válido y uno
inválido y comprobar el nuevo `track_id` y el error, respectivamente.

**Acceptance Scenarios**:

1. **Given** una sesión abierta, **When** se abre la sesión o el usuario pide actualizar el
   catálogo, **Then** el panel envía `list` y muestra los robots y pistas de `catalog` para elegir,
   marcando el robot y la pista vigentes.
2. **Given** una sesión sin corrida, **When** el usuario elige otro robot, **Then** el panel envía
   `load` y, al recibir el nuevo `hello` y `config`, actualiza los datos del robot, las
   capacidades y la forma de la visualización (p. ej. cantidad de sensores o si hay batería).
3. **Given** una sesión sin corrida, **When** el usuario elige una pista del catálogo y confirma el
   aviso de que se abrirá una sesión nueva, **Then** el panel se reconecta con los parámetros de
   conexión `track=<id>` y `robot=<robot vigente>` y muestra el `track_id` del nuevo `config`.
4. **Given** una sesión sin corrida, **When** el usuario selecciona un archivo JSON con una pista
   track v1, **Then** el panel envía `load_track` con su contenido y, al recibir `config`, muestra
   el nuevo `track_id` y limpia el rastro.
5. **Given** el usuario selecciona un archivo que no es JSON válido, **When** el panel intenta
   leerlo, **Then** muestra un error local claro y no envía nada.
6. **Given** el archivo es JSON pero no cumple track v1, **When** el servidor responde
   `invalid_track`, **Then** el panel muestra el error y la pista vigente no cambia.
7. **Given** una corrida activa, **When** el usuario intenta cambiar robot o pista, **Then** el
   panel impide la acción indicando que hay que detener la corrida (y, si el comando llegara a
   enviarse, muestra el `error` `run_active`).

---

### User Story 4 - Calibrar el perfil con valores medidos (Priority: P2)

El compañero que midió el robot físico (p. ej. el ruido de la regleta, la velocidad máxima o el
agarre lateral) carga esos valores medidos desde el panel para que la simulación se parezca al
robot real, y puede borrarlos para volver al valor por defecto.

**Why this priority**: acerca el simulador al robot real (principio V), pero depende de tener
mediciones; el ajuste del PID funciona sin ella.

**Independent Test**: con una sesión sin corrida, fijar un valor medido válido, comprobar el
`config` de respuesta y el valor marcado como "medido" en el panel; fijar un valor fuera de rango y
comprobar el error sin cambios; borrar el valor y comprobar que queda como "por defecto".

**Acceptance Scenarios**:

1. **Given** una sesión abierta, **When** el usuario abre la sección de calibración, **Then** ve
   los 12 parámetros físicos y de calibración que acepta `set_profile` (`sensor_pitch_m`,
   `sensor_offset_m`, `adc_white`, `adc_black`, `adc_noise`, `max_speed_mps`, `motor_tau_ms`,
   `wheelbase_m`, `max_lateral_accel_mps2`, `turbine_suction_n`, `encoder_ticks_per_rev`,
   `control_period_ms`), cada uno con un nombre legible en español, su unidad y su rango.
2. **Given** una sesión sin corrida, **When** el usuario ingresa uno o varios valores y los aplica,
   **Then** el panel envía un único `set_profile` con esos valores en `measured` y, al recibir
   `config`, marca esos parámetros como "medido" con el valor enviado.
3. **Given** un parámetro con valor medido, **When** el usuario lo borra, **Then** el panel envía
   `set_profile` con ese parámetro en `null` y, al recibir `config`, lo marca como "valor por
   defecto".
4. **Given** el usuario ingresa un valor que no es un número, **When** intenta aplicar, **Then** el
   panel lo señala en el campo y no envía nada.
5. **Given** el servidor rechaza el `set_profile` (`invalid_params` u `out_of_range`), **When**
   llega el `error`, **Then** el panel lo muestra y ningún parámetro cambia de estado (todo o nada,
   igual que el servidor).
6. **Given** el usuario carga otro robot con `load`, **When** llega el nuevo `hello`, **Then** el
   panel deja de mostrar valores medidos de la sesión anterior, porque el perfil se reinicializó.
7. **Given** una corrida activa, **When** el usuario intenta aplicar la calibración, **Then** el
   panel impide la acción indicando que hay que detener la corrida.

---

### Edge Cases

- **Robot real o capacidades distintas**: si `hello` indica `source = "robot"`, el panel oculta o
  deshabilita los controles solo-sim (`reset`, `load`, `set_profile`, `load_track`) y la vista del
  rastro (no hay `sim_truth`); si no hay `battery_v` o no hay `lap_timing`, oculta esos datos sin
  fallar. La regleta se dibuja con la cantidad de sensores y el rango ADC de `hello`.
- **Nuevo `hello` en mitad de la sesión** (tras `load`): todo lo siguiente se interpreta con ese
  `hello`; la visualización se rearma según sus capacidades.
- **Telemetría perdida**: si `seq` salta, el panel sigue funcionando y cuenta los mensajes
  perdidos (visible para el usuario); no espera reenvíos.
- **Frecuencia alta (100 Hz)**: el panel se mantiene fluido; puede refrescar la pantalla a menor
  ritmo que la telemetría, pero el rastro no debe perder puntos de forma visible.
- **Corridas largas**: el rastro conserva un número acotado de puntos (los más recientes) para no
  degradar la página; el historial de vueltas y la lista de resúmenes también tienen un tope
  razonable y muestran primero lo más reciente.
- **Línea perdida** (`line_lost = true`): se indica de forma visible en la regleta y en la posición
  de línea, distinguiéndola de una salida de pista.
- **`code` de error desconocido**: se muestra como error genérico con su `message`.
- **Mensaje con `type` desconocido o mensaje que no se puede interpretar**: el panel lo ignora sin
  romperse (y puede registrarlo como aviso).
- **Comandos con la conexión cerrada**: los controles quedan deshabilitados; nada se envía hasta
  reconectar.
- **Servidor lleno** (límite de sesiones alcanzado): si la conexión se rechaza o se cierra al
  abrirse, el panel muestra un mensaje claro de que no pudo conectarse y permite reintentar.
- **Varias pestañas**: cada pestaña abre su propia sesión independiente; lo que se haga en una no
  afecta a otra.
- **Recargar la página**: se pierde todo el historial (no se guardan datos) y se abre una sesión
  nueva.
- **Archivo de pista muy grande o con la extensión equivocada**: el panel intenta leerlo como JSON;
  si no lo es, muestra error local; si lo es, deja que el servidor decida si es una pista válida.

## Requirements *(mandatory)*

### Functional Requirements

**Entrega y conexión (P1)**

- **FR-001**: El servicio MUST entregar la página del panel en la ruta `/`, sin afectar a `/ws` ni
  a `/health`.
- **FR-002**: El panel MUST conectarse a `/ws` del mismo origen desde el que se cargó la página
  (seguro si la página es segura), sin que el usuario tenga que escribir ninguna dirección.
- **FR-003**: El panel MUST comunicarse con el simulador exclusivamente con los mensajes y comandos
  del contrato v1, sin parámetros, campos, rutas ni canales adicionales.
- **FR-004**: El panel MUST mostrar en todo momento el estado de la conexión (conectando,
  conectado, desconectado) y permitir reconectar cuando la conexión se cierra.
- **FR-005**: El panel MUST mostrar los datos del último `hello` (`session_id`, `source`,
  `robot.id`, `robot.firmware`, `robot.hw_rev` y todas las capacidades) y del último `config`.
- **FR-006**: El panel MUST interpretar cada mensaje según el último `hello` recibido y adaptar la
  visualización y los controles a sus capacidades (cantidad de sensores, bits del ADC, batería,
  `lap_timing`, `source`).

**Control de corridas (P1)**

- **FR-007**: El panel MUST permitir enviar `start`, `stop` y `reset`, habilitando cada acción solo
  cuando tiene sentido según el estado conocido (sin corrida / en corrida); `reset` solo con
  `source = "sim"`.
- **FR-008**: El panel MUST mostrar si hay corrida activa y su `run_id`, según `telemetry.running`
  y los eventos.

**Ajuste del controlador (P1)**

- **FR-009**: El panel MUST ofrecer para `kp`, `ki`, `kd` y `base_speed` un control deslizante y un
  campo numérico, inicializados con el último `config`.
- **FR-010**: Al cambiar uno de esos valores, el panel MUST enviar `set_config` con el campo
  cambiado, limitando el envío durante un arrastre continuo a unos pocos comandos por segundo y
  enviando siempre el valor final.
- **FR-011**: `base_speed` MUST limitarse a enteros de 0 a 255; `kp`, `ki` y `kd` a números ≥ 0. El
  recorrido de los controles deslizantes de `kp`, `ki` y `kd` MUST cubrir los valores habituales,
  y el campo numérico MUST aceptar cualquier valor ≥ 0.
- **FR-012**: El panel MUST permitir elegir la frecuencia de telemetría entre 10 y 100 Hz (enteros)
  y enviarla con `set_rate`.
- **FR-013**: Los controles MUST reflejar siempre los valores confirmados por el último `config`;
  ante un `error` deben volver a ellos.

**Visualización en vivo (P1)**

- **FR-014**: El panel MUST mostrar una barra con la lectura de cada sensor de la regleta, escalada
  al rango del ADC de `hello`, actualizada con cada telemetría que se dibuje.
- **FR-015**: El panel MUST mostrar `line_position` (con su ubicación sobre la regleta), `error` y
  `line_lost`.
- **FR-016**: El panel MUST mostrar los términos del PID (`p`, `i`, `d`, `out`) y el PWM de cada
  motor (izquierdo y derecho, −255 a 255, con su signo visible).
- **FR-017**: El panel MUST mostrar `battery_v` cuando está presente en la telemetría.
- **FR-018**: Con `source = "sim"`, el panel MUST dibujar el rastro del robot en el plano a partir
  de `sim_truth` (`x`, `y`), con su posición y orientación (`theta`) actuales, y mostrar
  `speed_mps` y `distance_m`. El rastro se limpia al empezar una corrida, al hacer `reset`, al
  cargar robot o pista y al reconectar. La escala del dibujo se ajusta al recorrido observado; no
  se dibuja la pista.
- **FR-019**: El panel MUST mostrar el `seq` de la última telemetría y la cantidad de telemetrías
  perdidas detectadas por saltos de `seq`.

**Vueltas, corridas y errores (P1)**

- **FR-020**: El panel MUST mostrar, para la corrida en curso, la vuelta actual y su tiempo
  (`telemetry.lap`) y el historial de vueltas completadas (`event lap`: número y duración).
- **FR-021**: El panel MUST indicar cada salida de pista (`event off_track`) con su `reason`.
- **FR-022**: El panel MUST conservar, durante la sesión, una lista de los resúmenes de las
  corridas terminadas (`run_finished.summary`: vueltas, mejor y promedio de vuelta, salidas de
  pista, pista, configuración inicial y `config_changed`), la más reciente primero, mostrando
  valores `null` como "—".
- **FR-023**: El panel MUST mostrar en pantalla cada `error` recibido (`code`, `message` y `cmd`) y
  los errores locales (p. ej. archivo inválido), de forma visible pero sin bloquear el uso.

**Robot y pista (P2)**

- **FR-024**: El panel MUST pedir el catálogo con `list` al abrirse la sesión y cuando el usuario lo
  pida, y mostrar robots y pistas para elegir.
- **FR-025**: Al elegir un robot, el panel MUST enviar `load` con su `robot_id`.
- **FR-026**: Al elegir una pista del catálogo, el panel MUST avisar que se abrirá una sesión nueva
  (se pierden el historial y la calibración de la sesión) y, si el usuario confirma, reconectarse a
  `/ws` con los parámetros de conexión del contrato `track=<id>` y `robot=<robot vigente>`. Si el
  servidor responde `unknown_track` o `unknown_robot`, MUST mostrar el error.
- **FR-027**: El panel MUST permitir seleccionar un archivo JSON local y enviarlo como `track` de
  `load_track`; si el archivo no es JSON válido, MUST mostrar un error local y no enviar nada.
- **FR-028**: Las acciones de robot y pista MUST estar disponibles solo sin corrida activa y con
  `source = "sim"`.

**Calibración (P2)**

- **FR-029**: El panel MUST mostrar los 12 parámetros que acepta `set_profile`, con nombre legible,
  unidad y rango según el contrato, y permitir ingresar un valor medido para cada uno.
- **FR-030**: Al aplicar, el panel MUST enviar un único `set_profile` con todos los valores
  ingresados en `measured` (enteros donde el contrato pide enteros) y validar localmente que sean
  números antes de enviar.
- **FR-031**: El panel MUST permitir borrar el valor medido de un parámetro, enviando `null` para
  ese parámetro.
- **FR-032**: El panel MUST marcar cada parámetro como "medido" (con el valor) o "por defecto",
  según los `set_profile` aceptados en la sesión; un `set_profile` rechazado no cambia ninguna
  marca, y un `load` aceptado las reinicia todas a "por defecto".
- **FR-033**: La calibración MUST estar disponible solo sin corrida activa y con `source = "sim"`.

**Calidad del ejemplo (todas las prioridades)**

- **FR-034**: Todos los textos del panel (etiquetas, estados, mensajes locales) MUST estar en
  español; los nombres de mensajes, campos y comandos del contrato se muestran tal cual.
- **FR-035**: El panel MUST seguir siendo usable si se ignoran todos los elementos solo-sim
  (principio II): con el robot real, conexión, control de corridas, ajuste del PID, visualización
  de sensores/PID/motores/batería, vueltas, resúmenes y errores funcionan igual.
- **FR-036**: El panel MUST NOT guardar datos entre recargas ni requerir cuentas de usuario.
- **FR-037**: Los comandos que envía el panel MUST validar contra el contrato v1; los tests MUST
  comprobarlo para cada comando que el panel puede enviar.

**Distribución y estilo (todas las prioridades)**

- **FR-038**: Distribución. El panel MUST organizarse como en el diseño de referencia, con una
  barra superior y tres columnas de tarjetas, adaptando el contenido al contrato:
  - **Barra superior** (de izquierda a derecha): marca y nombre del panel; estado de conexión;
    franja de métricas en línea (estado de la corrida y `run_id`, vuelta `lap.n`, tiempo de vuelta
    en curso `lap.current_ms`, `battery_v`, `rate_hz`, `track_id`, último `seq` y telemetrías
    perdidas); a la derecha, el robot (`robot.id`, `source`) como en el selector de piloto del
    diseño.
  - **Columna izquierda**, "lo que ve y decide el robot": tarjeta **Regleta** (barra de sensores,
    `line_position` sobre la regleta, `error`, `line_lost`); tarjeta **Controlador** (`p`, `i`,
    `d`, `out`) y **Motores** (PWM izquierdo y derecho); tarjeta **Registro** (eventos y errores).
  - **Columna central**, la más ancha: tarjeta **Rastro** (trayectoria de `sim_truth`, pose
    actual), con una franja inferior de valores como la del diseño: `speed_mps`, `distance_m`,
    `x`, `y`, `theta`.
  - **Columna derecha**, "lo que ajusta el usuario y los resultados": tarjeta **Control**
    (Iniciar, Detener, Reiniciar y los controles de `kp`, `ki`, `kd`, `base_speed` y frecuencia);
    tarjetas de **Vueltas** (vuelta actual, última, mejor y promedio, con el historial); tarjeta
    **Corridas** (resúmenes). **Robot y pista** y **Calibración** van en la tarjeta de Control
    como pestañas con el estilo de control segmentado del diseño.
- **FR-039**: Jerarquía. Los valores que se consultan durante una corrida (estado de corrida,
  `error`, regleta, PWM, vuelta actual y mejor vuelta) MUST tener el mayor tamaño y contraste; los
  datos de sesión (`session_id`, capacidades, `firmware`, `hw_rev`) MUST quedar en segundo plano,
  más chicos y tenues o en una sección plegable.
- **FR-040**: Números. Todo valor numérico MUST mostrarse en fuente monoespaciada con cifras de
  ancho fijo, alineado a la derecha y con su unidad junto al valor (`m`, `m/s`, `rad`, `V`, `ms`,
  `Hz`, `ADC`, `PWM`, milésimas de sensor). Cada magnitud MUST mostrarse con una cantidad fija de
  decimales y signo explícito cuando puede ser negativa (`error`, términos del PID, PWM), para que
  el texto no "salte" al actualizarse. Las unidades MUST ser las del contrato (SI y las excepciones
  del contrato), sin convertir a km/h ni otras.
- **FR-041**: Rótulos. Cada valor MUST llevar un rótulo corto en mayúsculas pequeñas y tenues, como
  en el diseño; los rótulos usan el nombre del campo del contrato o una abreviatura clara en
  español.
- **FR-042**: Color. MUST usarse la paleta del diseño (fondo casi negro, tarjetas apenas más
  claras, texto blanco y gris tenue, acento magenta/carmesí y acento azul claro). El magenta se
  reserva para la marca, el elemento activo y el rastro; el azul claro, para la mejor vuelta. Los
  estados MUST usar colores distintos del acento de marca (p. ej. ámbar para `line_lost`, rojo para
  `off_track` y `error`) y además texto o símbolo, para no depender solo del color. El texto MUST
  cumplir contraste mínimo AA sobre su fondo.
- **FR-043**: Sobriedad. El panel MUST NOT incluir fotografías, video, mapas de fondo, degradados,
  brillos, ilustraciones, íconos decorativos ni animaciones; solo cambian los valores y los
  gráficos cuando llegan datos. El rastro es una línea simple sin efectos.
- **FR-044**: Pantalla. En una pantalla de escritorio de 1440 × 900 o mayor, la vista principal
  (barra superior y las tres columnas) MUST verse completa sin desplazamiento; las pestañas de
  Robot y pista y de Calibración, el historial largo y los resúmenes pueden desplazarse dentro de su
  tarjeta. En pantallas más angostas, las columnas se apilan en el orden derecha (control),
  izquierda, centro, sin desplazamiento horizontal.
- **FR-045**: Vueltas objetivo. La tarjeta Control MUST ofrecer un campo opcional "vueltas
  objetivo" (entero ≥ 1). Es una regla del panel, no del contrato: el panel la aplica enviando
  `stop` como cualquier cliente.
  - Vacío significa sin límite: la corrida sigue hasta `stop` manual o salida de pista.
  - Con un valor, cuando las vueltas completadas de la corrida activa (`event lap` /
    `telemetry.lap.n`) alcanzan el objetivo, el panel MUST enviar `stop` una sola vez para esa
    corrida.
  - Detener MUST estar disponible siempre durante la corrida y puede cortarla antes de llegar al
    objetivo.
  - El campo puede cambiarse durante la corrida; si el nuevo valor ya es menor o igual que las
    vueltas completadas, el panel envía `stop` de inmediato. Un valor no entero o menor que 1 se
    señala en el campo y no se aplica.
  - La barra superior y la tarjeta de Vueltas muestran `lap.n / objetivo` (como `42 / 78` en el
    diseño), o solo `lap.n` si no hay objetivo.
  - Si `lap_timing = false` (sin vueltas), el campo se oculta.

### Key Entities

- **Sesión del panel**: la conexión abierta por una pestaña; tiene estado de conexión, último
  `hello`, último `config`, último `catalog` y si hay corrida activa.
- **Corrida observada**: desde `run_started` hasta `run_finished`; tiene `run_id`, rastro de
  posiciones, historial de vueltas y salidas de pista.
- **Resumen de corrida**: el `summary` de un `run_finished`, guardado en la lista de la sesión.
- **Rastro**: secuencia acotada de posiciones (`x`, `y`) tomadas de `sim_truth`.
- **Calibración de la sesión**: para cada uno de los 12 parámetros, si tiene valor medido enviado
  y aceptado en esta sesión, y cuál.
- **Registro de errores**: errores del servidor y locales, con hora de la sesión, el más reciente
  primero.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un compañero que nunca usó el panel abre la URL del simulador, inicia una corrida, ve
  el robot dando vueltas y obtiene el resumen en menos de 1 minuto, sin instrucciones previas.
- **SC-002**: Un cambio de `kp`, `ki`, `kd` o `base_speed` hecho en el panel se ve confirmado en
  pantalla en menos de 1 segundo.
- **SC-003**: Con telemetría a 100 Hz durante 5 minutos de corrida, el panel sigue respondiendo a
  los controles sin trabas perceptibles y no informa telemetrías perdidas por su propia causa en
  una conexión local.
- **SC-004**: El 100 % de los comandos que el panel puede enviar valida contra el contrato v1 en
  los tests, y el panel no usa ningún mensaje, campo o ruta fuera del contrato (salvo cargar la
  propia página).
- **SC-005**: El 100 % de los `error` provocados en las pruebas (valor fuera de rango, pista
  inválida, comando solo-sim durante una corrida, etc.) aparece en pantalla con su `code` y su
  mensaje.
- **SC-006**: Con un `hello` de robot real (`source = "robot"`, sin batería ni `lap_timing`), el
  panel funciona sin errores y oculta los controles solo-sim y los datos ausentes.
- **SC-007**: Un compañero del front puede identificar, leyendo el código del panel, cómo se
  conecta, cómo se envía cada comando y cómo se procesa cada tipo de mensaje en menos de 15
  minutos.
- **SC-008**: Durante una corrida, un usuario identifica en menos de 2 segundos de mirada si hay
  corrida activa, si la línea está perdida, el `error` actual y la mejor vuelta.
- **SC-009**: El 100 % de los valores numéricos visibles está en fuente monoespaciada y lleva su
  unidad (o es adimensional por contrato), y ninguno cambia de ancho al actualizarse.
- **SC-010**: La página no contiene ninguna imagen decorativa, video ni animación; una revisión
  lado a lado con `docs/design/reference.png` reconoce la misma paleta, acento de marca, estilo de
  rótulos y grilla de tres columnas.
- **SC-011**: Todo el texto del panel cumple contraste AA, y ningún estado (`line_lost`,
  `off_track`, `error`, conexión) se comunica solo con color.

## Assumptions

- **Valores del perfil no visibles por el contrato**: `config` no informa el perfil ni sus valores
  medidos o por defecto. Por eso el panel muestra como "medido" solo lo que él mismo envió y el
  servidor aceptó en esta sesión, y no muestra el valor por defecto ni el efectivo de cada
  parámetro (sí su unidad y rango, que son fijos en el contrato v1). Al abrir una sesión nueva,
  todos los parámetros se consideran "por defecto".
- **Cambiar a una pista del catálogo**: el contrato v1 no tiene un comando para cargar una pista
  del catálogo por id (`load_track` exige la pista completa y `load` solo cambia de robot); la
  pista inicial se elige con el parámetro de conexión `track`. Se asume que el panel cambia de
  pista del catálogo abriendo una sesión nueva con `?track=<id>` (y `?robot=<id>` vigente), lo que
  reinicia el historial de la sesión; el panel avisa de ello antes de hacerlo. Si se prefiere otro
  mecanismo, requiere ampliar el contrato en otra feature.
- La página es estática y se sirve junto con el simulador; no requiere instalar nada ni compilar
  del lado del usuario, y funciona en las versiones actuales de los navegadores de escritorio
  habituales. El uso en celular es deseable pero no prioritario.
- Recorrido por defecto de los controles deslizantes: `kp`, `ki`, `kd` de 0 a un máximo razonable
  para los valores por defecto del simulador (se fija en el plan), con paso fino; `base_speed` de
  0 a 255 de a 1; frecuencia de 10 a 100 Hz de a 1.
- El panel limita el envío de `set_config` durante un arrastre a unas 5 veces por segundo.
- Topes por defecto: el rastro guarda los últimos ~5 000 puntos; el historial de vueltas, las
  últimas 100 vueltas de la corrida; la lista de resúmenes, las últimas 50 corridas; el registro de
  errores, los últimos 50.
- No hay autenticación (igual que `/ws`); el panel es público para el equipo durante el desarrollo.
- Solo tema oscuro, como el diseño de referencia; no hay tema claro. Los valores exactos de color
  y las familias tipográficas se toman de `docs/design/reference.png` en el plan; la spec fija los
  roles (fondo, tarjeta, texto, tenue, acento de marca, acento de mejor tiempo, estados).
- La mejor vuelta, la última y el promedio de la corrida en curso los calcula el panel a partir de
  los `event lap` recibidos; al terminar la corrida se muestran los de `summary`.
- El acento magenta y la marca del diseño se adoptan como identidad visual del panel; no se usan
  el nombre "Velora GP" ni otros textos ficticios del diseño.
- La ruta `/` no forma parte del contrato v1 (como `/health`): es una ruta HTTP del servicio para
  entregar la página, no una interfaz de datos.
- Fuera de alcance: armar o editar perfiles de robot nuevos, dibujar la geometría de la pista (no
  viaja por el contrato), cuentas de usuario, guardar datos entre recargas, exportar telemetría y
  comparar corridas en gráficos.
