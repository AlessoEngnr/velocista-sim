# Research: Panel de laboratorio web

**Feature**: `003-panel-laboratorio` · **Fecha**: 2026-10-17 · **Plan**: [plan.md](./plan.md)

Cada decisión resuelve una incógnita del Technical Context o fija un detalle que la spec dejó
para el plan.

## R1. Entrega de la página: `StaticFiles` montado en `/`

- **Decisión**: `app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="panel")`,
  registrado **al final** de `create_app`, después de `GET /health` y `WS /ws`. `STATIC_DIR =
  Path(__file__).parent / "static"` (dentro del paquete `velocista_sim.server`). Con
  `html=True`, `GET /` devuelve `index.html`.
- **Razón**: Starlette resuelve las rutas en orden de registro; `/health` y `/ws` se encuentran
  antes que el montaje, y `StaticFiles` solo atiende scopes `http` (una conexión WebSocket a otra
  ruta no llega a él). Starlette 1.8 sirve archivos con `anyio`, sin `aiofiles`: **no hay
  dependencias nuevas de ejecución**. Al estar dentro de `src/velocista_sim/`, el `Dockerfile`
  (que copia `src/`) y el wheel de `uv_build` ya los incluyen.
- **Alternativas**: montar en `/static` y servir `index.html` con un `FileResponse` en `/`
  (dos mecanismos para lo mismo; el usuario pidió `StaticFiles` en `/`); carpeta `web/` en la raíz
  del repo (habría que tocar `Dockerfile` y buscarla subiendo directorios, como `config/`).

## R2. Tipo MIME de `.js` en Windows

- **Decisión**: en `server/app.py`, antes de montar, `mimetypes.add_type("text/javascript",
  ".js")` (y `"text/css", ".css"`). Un test verifica el `content-type` de cada recurso.
- **Razón**: Starlette usa `mimetypes.guess_type`, que en Windows lee el registro; hay equipos
  donde `.js` queda como `text/plain`, y el navegador **rechaza** módulos ES con un MIME que no
  sea JavaScript. El equipo desarrolla en Windows.
- **Alternativas**: un único script clásico sin módulos (evita el problema pero empeora la
  lectura del ejemplo, SC-007).

## R3. Organización del JavaScript: módulos ES nativos, sin build

- **Decisión**: `<script type="module" src="js/main.js">` y módulos chicos con una sola
  responsabilidad (ver estructura en [plan.md](./plan.md)): `connection.js` (WebSocket),
  `commands.js` (una función por comando del contrato, sin efectos), `state.js` (estado de la
  sesión y `applyMessage(state, message)` por `type`), `format.js`, `profile-params.js` y una
  carpeta `views/` con una función de render por tarjeta. Sin frameworks, sin dependencias de
  npm, sin `node`.
- **Razón**: SC-007 pide que el front del equipo entienda en < 15 min cómo se conecta, cómo se
  envía cada comando y cómo se procesa cada mensaje: tres archivos responden exactamente esas
  tres preguntas. Los módulos ES funcionan en todos los navegadores de escritorio actuales.
- **Alternativas**: un solo `panel.js` grande (más difícil de leer); Web Components (más
  ceremonia sin beneficio para una sola página).

## R4. URL del WebSocket y parámetros de conexión

- **Decisión**: `const scheme = location.protocol === "https:" ? "wss:" : "ws:"`;
  `new URL("/ws", `${scheme}//${location.host}`)`; para cambiar de pista se agregan solo
  `track` y `robot` con `url.searchParams` (FR-026). Nada más se agrega a la URL.
- **Razón**: FR-002 (mismo origen, seguro si la página es segura) y FR-003 (solo parámetros del
  contrato). Detrás del proxy de Railway la página llega por `https`, por eso `wss`.

## R5. Correlación de respuestas: cola FIFO de comandos pendientes

- **Decisión**: el contrato no tiene ids de petición, pero el servidor procesa los comandos en
  orden. El panel guarda una **cola de pendientes** solo con los comandos que, si se aceptan,
  responden con `config`: `set_config`, `set_rate`, `set_profile`, `load` (que responde
  `hello` y luego `config`) y `load_track`.
  - **`config`** → resuelve como **aceptado** el pendiente **más antiguo** de la cola (para
    `load`, el `hello` previo solo se aplica; el que resuelve es el `config`).
  - **`error` con `cmd`** → resuelve como **rechazado** el pendiente más antiguo cuyo `cmd`
    coincida con `error.cmd`. Si ninguno coincide, la cola no cambia.
  - **`start`, `stop`, `list` y `reset` no entran a la cola**: sus respuestas son `event`,
    `catalog` o nada (`reset` sin corrida no responde), y sus `error` solo se registran.
  - Los `error` sin `cmd` (p. ej. `unknown_track` de la conexión) no tocan la cola.
  - Un `config` con la cola vacía (el de apertura de sesión) solo actualiza el estado.

  Efectos de resolver un pendiente:
  - `set_profile` aceptado → marca "medido"/"por defecto" los parámetros enviados (FR-032);
    rechazado → ninguna marca cambia (todo o nada).
  - `load_track` aceptado → limpia el rastro (FR-018), aunque el `track_id` no cambie.
  - `set_config`/`set_rate` rechazados → los controles vuelven al último `config` (FR-013).
- **Razón**: es la única forma de atribuir respuestas usando solo el contrato (FR-003). Buscar
  el `error` por `cmd` (y no solo mirar la cabeza) evita desalinear la cola si un comando
  rechazado no era el más antiguo. La cola se vacía al cerrarse la conexión.
- **Alternativas**: comparar el `config` recibido con lo enviado (falla si el valor no cambió o si
  `set_profile` no se refleja en `config`, que no informa el perfil); bloquear la UI hasta cada
  respuesta (peor al arrastrar sliders).

## R6. Frecuencia de render y telemetría a 100 Hz

- **Decisión**: cada mensaje se aplica al estado **en el momento** (`onmessage`): se cuentan los
  saltos de `seq`, se agrega el punto de `sim_truth` al rastro y se procesan eventos. El dibujo
  (DOM y canvas) se hace como mucho una vez por cuadro con `requestAnimationFrame` y una marca de
  "sucio". Los textos se escriben con `textContent` solo si cambiaron.
- **Razón**: SC-003 (5 min a 100 Hz sin trabas) y el borde "el rastro no debe perder puntos":
  los puntos se guardan siempre aunque la pantalla se refresque a 60 Hz. El navegador no pierde
  frames de WebSocket por renderizar lento: los `seq` perdidos serían del servidor (cola llena),
  no "por causa propia" del panel.

## R7. Canvas 2D: regleta y rastro

- **Decisión**:
  - **Regleta**: un `<canvas>` con una barra vertical por sensor (`line_sensors` barras), altura
    = lectura / (2^`adc_bits` − 1); marcador vertical de `line_position` en x =
    `line_position / ((n − 1) × 1000)`; con `line_lost` el marcador se dibuja en ámbar discontinuo
    y aparece el texto `LÍNEA PERDIDA` (no solo color, FR-042).
  - **Rastro**: buffer circular de 5 000 puntos en dos `Float32Array` (`x`, `y`); la escala se
    ajusta a la caja que contiene todos los puntos guardados (con margen y misma escala en x e y,
    eje y hacia arriba); polilínea de 1,5 px en el acento magenta, sin brillo; la pose actual es un
    triángulo blanco orientado por `theta`. Se redibuja entero en cada cuadro sucio (5 000
    segmentos es trivial para Canvas 2D).
  - Ambos canvas escalan por `devicePixelRatio` y se redimensionan con `ResizeObserver`.
  - **Limpieza**: el rastro se limpia **en cada `start`** (al enviarlo desde Iniciar), además de
    los casos de FR-018 (`reset`, `load`/`load_track` aceptados, sesión nueva). La tarjeta Rastro
    tiene un botón **Limpiar rastro** que lo vacía a mano en cualquier momento; es una acción
    local, no envía nada.
- **Razón**: FR-014, FR-015, FR-018 y los topes de la spec; Canvas 2D sin librerías, como pidió el
  usuario.
- **Alternativas**: SVG (miles de nodos o un `path` enorme reescrito 60 veces por segundo).

## R8. Envío limitado de `set_config` al arrastrar

- **Decisión**: un *throttle* por campo de 200 ms (≤ 5 comandos/s) con envío inicial y envío
  final garantizado (`trailing`) al soltar o al dejar de mover. El campo numérico envía en
  `change` (al confirmar), sin throttle. Cada envío lleva solo el campo cambiado
  (`{"cmd":"set_config","params":{"kp":…}}` o `{"cmd":"set_config","base_speed":…}`).
  `set_rate` se envía en `change`.
- **Razón**: FR-010 y la suposición de "unas 5 veces por segundo"; SC-002 (< 1 s) se cumple de
  sobra.

## R9. Rangos de los controles deslizantes

- **Decisión** (los campos numéricos aceptan cualquier valor ≥ 0; FR-011):

  | Control | Rango del slider | Paso | Decimales mostrados |
  |---|---|---|---|
  | `kp` | 0 – 0.2 | 0.0005 | 4 |
  | `ki` | 0 – 0.01 | 0.0001 | 4 |
  | `kd` | 0 – 5 | 0.01 | 4 |
  | `base_speed` | 0 – 255 | 1 | 0 |
  | `rate_hz` | 10 – 100 | 1 | 0 |

- **Razón**: con 16 sensores el `error` llega a ±7 500; con `kp = 0.045` (defecto) el término P
  ya satura el PWM (≈ 340). Un recorrido hasta ~4× el defecto de `kp` y ~5× el de `kd` cubre los
  valores habituales con paso fino. Si `config` informa un valor fuera del recorrido, el slider
  queda en el extremo y el campo numérico muestra el valor real.

## R10. Formato de números y unidades

- **Decisión**: `format.js` centraliza una función por magnitud, con decimales fijos y signo
  explícito (`+`/`−` con el signo menos tipográfico U+2212) cuando puede ser negativa:

  | Magnitud | Formato | Unidad mostrada |
  |---|---|---|
  | `error`, `line_position` | entero, `error` con signo | `‰ sensor` (milésimas de sensor) |
  | `sensors[i]` | entero | `ADC` |
  | `control.p/i/d/out` | 1 decimal, con signo | — (adimensional en el contrato) |
  | `motors.left/right` | entero con signo | `PWM` |
  | `battery_v` | 2 decimales | `V` |
  | `speed_mps` | 2 decimales | `m/s` |
  | `distance_m` | 2 decimales | `m` |
  | `x`, `y` | 3 decimales, con signo | `m` |
  | `theta` | 3 decimales, con signo | `rad` |
  | `lap.current_ms`, `lap_ms`, `best/avg_lap_ms` | segundos con 3 decimales | `s` |
  | `rate_hz` | entero | `Hz` |
  | `t_ms` del registro | segundos con 3 decimales | `s` |

  `null` o ausente → `—`. CSS: `font-family: var(--font-mono)`, `font-variant-numeric:
  tabular-nums`, alineado a la derecha y `min-width` en `ch` por valor para que no cambie de
  ancho (SC-009).
- **Razón**: FR-040. Mostrar tiempos en segundos sigue siendo SI (el contrato solo **transporta**
  ms como excepción); se lee mejor que `72634 ms` y coincide con el diseño (`1:12.634`).
  No se convierte a km/h ni a otras unidades.

## R11. Tipografía y paleta

- **Decisión**: solo fuentes del sistema (sin descargas externas):
  - `--font-sans: system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
  - `--font-mono: ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, "Liberation Mono",
    monospace`

  Paleta tomada de `docs/design/reference.png` (solo tema oscuro), contraste calculado con la
  fórmula WCAG sobre tarjeta `#15151a`:

  | Token | Valor | Uso | Contraste |
  |---|---|---|---|
  | `--bg` | `#0b0b0e` | fondo de página | — |
  | `--card` | `#15151a` | tarjetas | — |
  | `--raised` | `#1d1d24` | control segmentado, campos | — |
  | `--border` | `#26262e` | bordes sutiles | — |
  | `--text` | `#f2f2f4` | valores | 16.3:1 |
  | `--muted` | `#8e8e99` | rótulos | 5.6:1 |
  | `--accent` | `#e5336d` | marca, rastro, elemento activo (no texto chico) | 4.35:1 (≥ 3:1 gráfico) |
  | `--accent-text` | `#f0517f` | texto en acento | 5.4:1 |
  | `--best` | `#8cc4f2` | mejor vuelta | 9.8:1 |
  | `--warn` | `#f2b33d` | `line_lost` | 9.8:1 |
  | `--danger` | `#ff6b5e` | `off_track`, `error`, desconectado | 6.5:1 |
  | `--ok` | `#4fd18b` | conectado / en corrida | 9.4:1 |

  Botón primario: texto blanco sobre `#c81e57` (5.6:1). Cada estado lleva además texto o símbolo
  (`● CONECTADO`, `▲ LÍNEA PERDIDA`, `✕ FUERA DE PISTA`). El punto "LIVE" es estático (FR-043).
- **Razón**: FR-042, SC-011; no cargar fuentes externas evita rutas fuera del servicio (FR-003).
- **Alternativas**: una fuente geométrica de Google Fonts (dependencia externa en tiempo de
  ejecución, no funciona sin internet).

## R12. Pruebas de navegador con Playwright

- **Decisión**: dependencia **solo de desarrollo** `playwright` (Python, API síncrona) agregada
  con `uv add --dev playwright`; los navegadores se instalan aparte con
  `uv run playwright install chromium` (en CI, `--with-deps`). Sin `pytest-playwright`: un fixture
  propio en `tests/browser/conftest.py` lanza Chromium headless y abre una página.
  - El servidor de prueba es un `uvicorn` real en un hilo y puerto libre, igual que en
    `tests/integration/test_health_client.py`; ese fixture se mueve a
    `tests/support/live_server.py` y lo usan ambos.
  - Marcador `browser`. Si Chromium no está instalado, los tests se **omiten** con un motivo que
    indica el comando de instalación; con `VELOCISTA_REQUIRE_BROWSER=1` (lo fija la CI) la falta
    del navegador es un **fallo**, para que la CI no los saltee en silencio.
  - Los frames enviados y recibidos se capturan con `page.on("websocket")` →
    `framesent`/`framereceived`; cada comando enviado se valida con `validate_command` y cada
    mensaje recibido con `validate_message` y el último `hello` (principio VII).
- **Razón**: el usuario pidió un test de humo con Playwright contra un servidor local; la
  dependencia no llega a la imagen (`uv sync --no-dev`) ni al servidor.
- **Alternativas**: `pytest-playwright` (fixtures listas, pero agrega `pytest-base-url` y
  opciones de CLI que no se necesitan); Selenium (más pesado, sin captura de frames WS).

## R13. Cobertura de FR-037 (todo comando del panel valida contra el contrato)

- **Decisión**: `commands.js` es la **única** vía de construir comandos. Un test de navegador
  importa ese módulo en la página (`await import("/js/commands.js")`), construye un ejemplo de
  cada uno de los 9 comandos con argumentos representativos (incluido `set_profile` con un valor y
  con `null`, y `set_config` con cada campo) y los valida en Python con `validate_command`. El
  test falla si `commands.js` exporta un constructor sin caso de prueba. El test de humo, además,
  valida todo frame realmente enviado.
- **Razón**: FR-037 y SC-004 exigen el 100 % de los comandos; hacerlo por la UI completa
  multiplicaría el tiempo del test sin cubrir más el contrato.

## R14. Robot real sin hardware (SC-006)

- **Decisión**: un test de navegador usa `page.route_web_socket("**/ws", handler)` de Playwright
  para hacer de "robot real": envía un `hello` con `source = "robot"`, `lap_timing = false`,
  `battery.voltage_sense = false`, un `config` con `track_id = null` y telemetría sin
  `sim_truth`/`lap`/`battery_v`. Verifica que no hay errores de consola, que los controles
  solo-sim y el rastro están ocultos y que Iniciar sigue enviando `start`. Los mensajes del falso
  robot se validan con `validate_message` antes de enviarlos.
- **Razón**: SC-006 y principio II sin necesitar el robot físico; no toca el servidor.

## R15. Reconexión y servidor lleno

- **Decisión**: sin reconexión automática; al cerrarse el socket el panel muestra
  `DESCONECTADO` y un botón **Reconectar**. Si el cierre trae código 1013 (sesiones al máximo) el
  mensaje es "Servidor lleno: no se pudo abrir la sesión. Reintentar más tarde"; con 1008, "El
  servidor cerró la sesión porque el panel no leía a tiempo". Al reconectar se descarta todo el
  estado de la sesión anterior: rastro, vueltas, cola de pendientes, calibración, contadores de
  `seq` y **también los resúmenes de corridas**. Solo el **registro** de eventos y errores se
  conserva en pantalla hasta recargar la página.

  > Nota: la spec pide tratar la nueva sesión "como nueva (nuevo `hello`, nuevo `config`,
  > rastro limpio)" y FR-022 define los resúmenes como "de la sesión"; por eso se borran al
  > reconectar, para no mezclar `run_id` de sesiones distintas. El registro se conserva porque
  > incluye el aviso de desconexión y lo ocurrido antes de reconectar.
- **Razón**: FR-004 y el borde "servidor lleno"; reintentar en bucle contra un servidor lleno
  solo empeora la situación.

## R16. Vueltas objetivo (FR-045)

- **Decisión**: estado `lapTarget` (entero ≥ 1 o `null`) y `stopSentFor` (`run_id` al que ya se
  le envió `stop` automático). Tras cada `event lap` o `telemetry.lap.n`, y al cambiar el campo,
  si hay corrida activa, `completed ≥ lapTarget` y `stopSentFor !== run_id` → se envía `stop` y se
  guarda `stopSentFor = run_id`. Un valor no entero o < 1 marca el campo inválido
  (`aria-invalid`) y no cambia `lapTarget`. Con `lap_timing = false` el campo se oculta.
- **Razón**: garantiza el "una sola vez por corrida" aunque lleguen varias telemetrías con el
  mismo `lap.n` antes del `run_finished`.
