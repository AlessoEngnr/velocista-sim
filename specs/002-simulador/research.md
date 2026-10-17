# Research: Simulador de velocista accesible por WebSocket

Decisiones técnicas de la fase 0. No quedan `NEEDS CLARIFICATION`. Los valores numéricos que la
spec dejaba "para el plan" (umbrales de salida de pista, PID por defecto, pista por defecto,
batería) se fijaron con un prototipo descartable de la física (scratchpad, no versionado):

| Caso del prototipo (dt 2 ms, perfil velocista-01) | Resultado |
|---|---|
| Estadio 1,5 m + r 0,6 m, kp 0,045 · ki 0 · kd 0,9 · base 180 | 3 vueltas en 10,30 s (≈ 3,42 s/vuelta), a_lat máx 6,8 m/s² |
| Mismo, con un corte de 0,02 m en recta o en curva | sin `off_track` |
| Mismo, base 255 | sigue la línea derrapando (a_lat recortada a 9,0) |
| Estadio del ejemplo `oval-small` (0,4 m + r 0,25 m), config por defecto | 5 vueltas en 7,4 s, a_lat saturada en 9,0 |
| kp = ki = kd = 0 | `off_track` a los 0,92 s |
| kp = 0, kd = 0,9 | `off_track` a los 1,54 s |
| Velocidad del prototipo en Python puro | ≈ 2.300 pasos/s (insuficiente: 5 sesiones necesitan 2.500) |

---

## R1. Núcleo de sesión sin E/S + adaptador asyncio

- **Decisión**: `server.session.Session` es una clase síncrona: `open() -> mensajes`,
  `submit(frame: str)` (encola), `step() -> mensajes`. No conoce asyncio, sockets ni el reloj.
  `server.pacer` ejecuta `step()` al ritmo del reloj y `server.app` conecta el WebSocket.
- **Razón**: cumple el principio VI por construcción (el resultado depende solo de la secuencia
  de pasos y de en qué paso entra cada comando); permite tests deterministas y rápidos
  (10 s simulados en < 1 s) y reproducibilidad exacta (SC-003).
- **Alternativas**: lógica dentro del handler del WebSocket (mezcla tiempo real con simulación,
  no reproducible); un hilo por sesión (innecesario con asyncio y más difícil de testear).

## R2. Separación mundo / robot / servidor

- **Decisión**: tres paquetes. `world` y `robot` no se importan entre sí ni importan `server`;
  `server.session` es el único que los conoce y hace de "bus": `world.read_sensors()` →
  `list[int]` → `robot.tick(sensors)` → `(left, right)` → `world.set_motor_pwm(left, right)`.
  `tests/unit/test_architecture.py` recorre con `ast` los `.py` de `world/` y `robot/` y falla
  si `robot` importa `velocista_sim.world`/`server`, si `world` importa `robot`/`server`, o si
  cualquiera importa `time`, `datetime`, `random` o `asyncio`.
- **Razón**: principio III y FR-017/FR-040 verificables automáticamente.
- **Alternativas**: un solo paquete `sim` con convenciones (no verificable); import-linter
  (dependencia extra para una regla que un test de 30 líneas cubre).

## R3. Cálculo de lecturas de la regleta (numpy + grilla espacial)

- **Decisión**: al cargar una pista, `TrackGeometry` corta la `centerline` en los cortes
  (`gaps`) y guarda los **tramos con tinta** como arrays numpy `(M, 2)` de extremos A y B, más
  una grilla uniforme de celdas de 0,05 m que lista qué tramos tocan cada celda. Para leer la
  regleta: se calculan las 16 posiciones de sensor (vectorizado), se juntan los tramos de las
  celdas que cubren la caja de la regleta y se calcula la distancia punto–segmento de 16 × K en
  una sola operación numpy. Cobertura de cada sensor (apertura `a = sensor_pitch_m`):
  `cov = clip((line_width/2 + a/2 − d) / a, 0, 1)`; lectura
  `round(adc_white + (adc_black − adc_white)·cov + ruido)`, recortada a `0 … 2^adc_bits − 1`.
- **Razón**: el prototipo en Python puro da ≈ 2.300 pasos/s; numpy con la grilla apunta a
  ≥ 10.000 pasos/s por sesión. La grilla es global (funciona con pistas que se cruzan o con el
  robot lejos de donde estaba), y los cortes salen naturalmente porque no tienen tinta. La
  rampa lineal da valores intermedios continuos (FR-012) y una `line_position` suave.
- **Alternativas**: búsqueda local por ventana de índices (falla en cruces y al salir de la
  línea); mapa de distancias rasterizado (≈ 8 MB por pista a 2 mm y menos preciso en el borde de
  la línea); Python puro (no alcanza el rendimiento). **Dependencia nueva**: `uv add numpy`.

## R4. Física del mundo

- **Decisión** (paso `dt = 0,002 s`, constantes del perfil efectivo):
  1. Velocidad pedida por rueda: `v_cmd = pwm / 255 · max_speed_mps` (proporcional, sin zona
     muerta; spec, Assumptions).
  2. Motor de primer orden, discretización exacta:
     `v += (v_cmd − v) · (1 − exp(−dt / τ))`, con `τ = motor_tau_ms / 1000`.
  3. Cinemática diferencial: `v = (v_l + v_r)/2`, `ω = (v_r − v_l)/wheelbase_m`.
  4. Agarre: si `|v·ω| > max_lateral_accel_mps2` y `|v| > 0`, se recorta
     `ω = sign(ω)·a_max/|v|`: el robot gira menos de lo pedido y la trayectoria se abre hacia
     afuera de la curva (FR-011).
  5. Integración: `θ += ω·dt`; `x += v·cos θ·dt`; `y += v·sin θ·dt`;
     `distance_m += |v|·dt`. `theta` se informa normalizado a (−π, π].
- **Razón**: modelo mínimo que cubre lo pedido (FR-010, FR-011) y que el prototipo validó con la
  config por defecto.
- **Alternativas**: modelo dinámico con fricción de neumático (sobredimensionado para v1);
  integrar a otro `dt` (la constitución fija pasos de `dt`; 2 ms ≪ τ = 45 ms).

## R5. Tiempo: pasos, `t_ms`, control y telemetría

- **Decisión**: `DT_MS = 2` (constante). `t_ms = paso · 2`, entero, tiempo **simulado** de la
  sesión; `hello` y `config` iniciales con `t_ms = 0`. Calendarios con aritmética entera o con
  índice de tick para evitar deriva:
  - Control: tick cuando `t_ms ≥ t0 + k · control_period_ms` (k = 1, 2, …). Con el valor por
    defecto (2 ms) corre en todos los pasos; con periodos no múltiplos de 2 ms el periodo
    efectivo queda cuantizado a `dt`. El calendario se reinicia en `start` y al cambiar el perfil.
  - Telemetría: se emite en el paso en que `(t_ms − t_rate)·rate_hz ≥ k·1000`; `set_rate`
    reinicia el calendario (`t_rate = t_ms`, k = 1). 50 Hz → cada 10 pasos.
- **Razón**: `t_ms` no decreciente y reproducible; como el `Pacer` mantiene tiempo real, coincide
  con el tiempo de pared salvo atrasos acotados.
- **Alternativas**: `t_ms` del reloj de pared (no reproducible, rompe SC-003).

## R6. Semilla y ruido

- **Decisión**: semilla base de la sesión = `VELOCISTA_SEED` (entero, por defecto `1`; igual para
  todas las sesiones). La semilla de **cada corrida** se deriva del par
  (semilla base, número de corrida en la sesión): en cada `start` aceptado se crea un generador
  nuevo `numpy.random.Generator(PCG64(SeedSequence([seed, n])))`, con `n = 1, 2, …` (el mismo `n`
  del `run_id` `"r-<n>"`). Fuera de corrida (sesión recién abierta o entre corridas) se usa un
  generador aparte derivado de `[seed, 0]`, que no influye en ninguna corrida. Ruido: entero
  uniforme en `[−adc_noise, +adc_noise]` por sensor y por lectura. Solo el mundo consume el
  generador (el ruido es física del sensor).
- **Razón**: cada corrida tiene ruido distinto (el optimizador no se ajusta a un único patrón de
  ruido), pero la secuencia completa es reproducible: como `start` también reinicia pose, motores
  y PID (FR-021), la corrida `n` es función pura de (semilla base, `n`, perfil, pista, config,
  comandos durante la corrida), sin importar cuánto tiempo ocioso hubo antes de `start`. Dos
  sesiones que hacen la misma secuencia de corridas obtienen los mismos `summary` (SC-003), incluso
  por WebSocket. `SeedSequence` mezcla el par sin correlación entre corridas consecutivas (a
  diferencia de `seed + n`).
- **Alternativas**: re-sembrar con la misma semilla en cada `start` (todas las corridas con el
  mismo ruido: el optimizador podría sobreajustarse a él); un solo flujo por sesión (el resultado
  dependería del tiempo ocioso antes de `start`, que viene del reloj); semilla elegida por el
  cliente (el contrato v1 no la define).

## R7. Robot a bordo: línea y PID

- **Decisión**:
  - Sensores con índice 0 a la **izquierda** del robot (eje y del cuerpo) y 15 a la derecha;
    regleta centrada a `sensor_offset_m` delante del eje, sensores cada `sensor_pitch_m`.
  - Normalización con la calibración propia: `n_i = clip((s_i − adc_white)/(adc_black − adc_white), 0, 1)`;
    `n_i < 0,1` se toma 0 (piso de ruido). Si `adc_black == adc_white`, todo `n_i = 0`.
  - `line_lost = Σ n_i < 0,3`. Si no: `line_position = round(1000 · Σ i·n_i / Σ n_i)` y se
    guarda como última; si se perdió: `0` si la última fue `< centro`, si no
    `(N−1)·1000` (FR-018). `error = line_position − (N−1)·500`.
  - PID discreto por tick de control (convención habitual de velocistas, sin dividir por el
    periodo): `p = kp·e`; `I += e`, `i = ki·I`; `d = kd·(e − e_prev)` con `e_prev = e` en el
    primer tick (sin patada); `out = p + i + d`.
    `left = clip(round(base_speed + out), −255, 255)`, `right = clip(round(base_speed − out), −255, 255)`
    (error positivo = línea a la derecha → girar a la derecha).
  - Sin corrida: se leen sensores y se calcula la línea, pero el PID no corre:
    `control = {p,i,d,out} = 0`, motores 0 (FR-020).
  - `p`, `i`, `d` y `out` se acotan a ±1e9 antes de informarlos, para que valores extremos de
    `kp/ki/kd` nunca produzcan números no finitos en JSON.
- **Razón**: con estas convenciones las ganancias del ejemplo `pdf-config` del contrato
  (kp 0,045 · kd 0,9) siguen el óvalo en el prototipo. Sin anti-windup en v1 (ki por defecto 0).
- **Alternativas**: PID en unidades de tiempo (`ki·∫e dt`, `kd·de/dt`): cambiaría la escala de
  las ganancias respecto del ejemplo del contrato y del firmware habitual.

## R8. Validación de comandos y códigos de error

- **Decisión**: `server.commands.parse(frame)`:
  1. `json.loads` con `parse_constant` que rechaza `NaN`/`Infinity`; error de parseo o no-objeto
     → `invalid_json` (sin `cmd`).
  2. Si trae `v` y `v != 1` (cualquier tipo) → `unsupported_version` (con `cmd` si es string).
  3. `cmd` ausente, no string o desconocido → `unknown_cmd`.
  4. `validate_command(frame)` y mapeo de la **primera** violación por prioridad:
     violaciones bajo `/track/…` de `load_track` (con `track` presente y objeto) → `invalid_track`;
     `required`, `type`, `enum`, `const`, `minProperties`, `propertyNames`, `not`, `anyOf`,
     `oneOf` → `invalid_params`; `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum` →
     `out_of_range`. Si hay de ambos tipos, gana `invalid_params`.
  5. Reglas de estado en la sesión: `start` activo → `run_active`; `stop` inactivo → `no_run`;
     `reset`/`load`/`set_profile`/`load_track` con corrida → `run_active`; `load` con ID fuera del
     catálogo → `unknown_robot`.
  Todo `error` lleva `message` en español; nada cambia en la sesión (FR-031, SC-007).
- **Razón**: reutiliza `velocista_sim.contract` (una sola fuente de reglas) y produce exactamente
  los códigos de la tabla del contrato (`set_profile` de un parámetro de `hello` → `enum` en
  `/measured` → `invalid_params`; `wheelbase_m` negativo → `exclusiveMinimum` → `out_of_range`).
- **Alternativas**: validar con modelos Pydantic (duplicaría el contrato y divergiría).

## R9. Detección de vueltas y de salida de pista

- **Decisión** (en el mundo, solo con corrida activa, después de cada paso de física):
  - **Progreso**: proyección del eje sobre la `centerline` completa (sin descontar cortes),
    buscada en una ventana de índices alrededor de la última proyección; el avance por paso se
    "desenvuelve" en `(−L/2, L/2]` y se acumula desde la salida. Al `start` el robot queda con el
    eje sobre `start.at`, orientado según la tangente en el sentido de avance.
  - **Vuelta** (solo pistas `closed`): cuando el progreso acumulado alcanza `(n+1)·L` se completa
    la vuelta `n+1`; `lap_ms = t_ms − t_inicio_vuelta`. Retroceder descuenta progreso, así que
    pasar la salida en reversa no cuenta.
  - **Salida de pista**: la regleta "ve tinta" si algún sensor tiene cobertura > 0 (verdad sin
    ruido). Mientras no la ve se acumulan la distancia recorrida por el **centro de la regleta**
    (`|v|·dt + |ω|·sensor_offset·dt`) y el tiempo. `off_track` si la distancia supera
    **0,10 m** o el tiempo supera **1,0 s**; o de inmediato si el eje sale del tablero
    `[0, width] × [0, height]`. Siempre `reason = "line_lost"`.
- **Razón**: un corte típico (≤ 0,05 m) se cruza con `line_lost` breve sin `off_track`
  (verificado en el prototipo con 0,02 m); 0,10 m es el orden que fija la spec. La distancia de
  la regleta (no del eje) detecta también al robot que gira en el lugar; el tope de tiempo cubre
  al robot que quedó quieto sin ver la línea. Un robot quieto **sobre** la línea nunca termina.
- **Alternativas**: usar `line_lost` del robot (mezclaría el controlador con la detección del
  mundo y depende del ruido); distancia a la línea central > ancho de la regleta como única regla
  (no distingue bien los cortes en curva).

## R10. Tests: TestClient con reloj acelerado y validación de cada mensaje

- **Decisión**:
  - `create_app(settings, clock=None)`: el `Pacer` recibe un reloj inyectable (por defecto
    `time.monotonic`). Los tests de WebSocket usan `TestClient` con un reloj acelerado (×20) para
    que una corrida de 3 vueltas tarde < 1 s real; el resultado de la simulación no cambia.
  - `tests/support/contract_client.py` envuelve la conexión de `TestClient`: cada `receive_json`
    valida con `validate_message(msg, ultimo_hello)` y además comprueba las reglas de secuencia
    que el validador no cubre (primer mensaje `hello`, luego `config`; `t_ms` no decreciente;
    `seq` creciente desde 0, con saltos solo si se permite descarte; exactamente un
    `run_finished` por `run_id`; `off_track` seguido de `run_finished`; ningún mensaje con
    `centerline`). Cualquier violación hace fallar el test (principio VII, SC-002).
  - Los mismos chequeos se aplican a los mensajes del núcleo `Session` en los tests sin E/S.
  - Un test de cobertura autónomo (no depende del orden ni de otros tests) corre un guion fijo
    y comprueba que se emiten y validan al menos una vez cada `type`, cada `event` y cada `code`
    de error alcanzable en el simulador (todos menos `sim_only`).
- **Razón**: es lo pedido (TestClient + `velocista_sim.contract`) y mantiene la suite rápida.
- **Alternativas**: solo tests de núcleo (no prueban el transporte); tiempo real en todos los
  tests (suite de minutos). **Dependencia nueva de dev**: `uv add --dev httpx` (requerida por
  `fastapi.testclient`).

## R11. Ritmo en tiempo real, cola de salida y cliente lento

- **Decisión**: por sesión, dos tareas asyncio:
  - **Pacer**: `objetivo = floor((reloj − t_base)/0,002)`; ejecuta pasos hasta alcanzarlo, como
    máximo 50 por tanda (100 ms); si el atraso supera 100 ms, mueve `t_base` (la simulación se
    enlentece en vez de "ponerse al día" a ráfagas). Entre tandas, `asyncio.sleep` hasta el
    próximo paso de telemetría o 5 ms, lo que sea menor. Los frames recibidos se encolan y se
    aplican todos al inicio del paso siguiente (FR-032).
  - **Sender**: vacía la cola de salida con `send_text`. Al encolar un `telemetry`, si ya hay
    25 `telemetry` pendientes se descarta (el `seq` igual se consumió: el cliente ve el salto).
    `event`, `config`, `error`, `catalog` y `hello` nunca se descartan; si su backlog supera
    1.000 mensajes (cliente que no lee y envía comandos), se cierra la conexión con código 1008.
  - Ping/pong del WebSocket: el de uvicorn (20 s), sin keepalive propio (contrato).
  - Desconexión: se cancelan ambas tareas y la sesión se descarta; sin `run_finished` (FR-026).
- **Razón**: el simulador nunca espera al cliente; las sesiones no comparten estado; en Windows
  (resolución de timer ≈ 15 ms) las tandas son más grandes pero la tasa promedio se mantiene
  (SC-004 mide promedio en 10 s).
- **Alternativas**: un ticker global para todas las sesiones (acopla sesiones: una lenta frena a
  todas); `await send` dentro del paso (el cliente lento frenaría la simulación).

## R12. Catálogo, perfil y pista por defecto

- **Decisión**:
  - `config/robots/<id>.json`: perfil del robot con la forma de `robot-profile.schema.json`.
    `velocista-01.json` es copia exacta del `message` de
    `contract/examples/valid/robot-profile/velocista-01-default.json`.
  - `config/tracks/<id>.json`: pista track v1. `oval-01.json`: estadio cerrado centrado en
    (1,50; 1,25) en un tablero de 3,00 × 2,50 m, rectas de 1,50 m y radio 0,60 m
    (L ≈ 6,770 m, 1354 puntos cada ≈ 5,000 mm), `line_width` 0,019, sin `gaps`,
    `start.at = 0,10` sobre la recta inferior (sentido antihorario), `rules_profile` `"lgr2026"`.
    Se genera con el mismo procedimiento que `oval-small` del contrato, con el script versionado
    `tools/gen_oval.py`, y se versionan el script y el JSON (regenerable byte a byte). No se usa `oval-small` tal cual como pista por
    defecto porque sus curvas de 0,25 m saturan el agarre con la config por defecto (frágil ante
    un `max_lateral_accel_mps2` medido menor) y tiene un corte, y la spec pide un óvalo sin
    cortes; `oval-small` sí se reutiliza en los tests por `load_track` (cortes, SC-005).
  - Al arrancar, el servidor valida cada archivo (`validate_profile`/`validate_track`) y exige
    que el nombre coincida con el `id`, y que el perfil tenga `encoders`, `imu` y `turbine` en
    `false` y `motors = 2` (el simulador v1 no los simula): si algo falla, no arranca.
  - Config inicial de cada sesión: `controller "pid"`, `kp 0,045`, `ki 0`, `kd 0,9`,
    `base_speed 180`, `rate_hz 50` (los del ejemplo `pdf-config` del contrato; validados por el
    prototipo: 3 vueltas en ≈ 10,3 s).
  - `load` reemplaza el perfil (sin los `measured` de `set_profile` previos), conserva
    `config`, `rate_hz` y pista, y deja el robot en la salida. `set_profile` no mueve el robot.
    Las pistas de `load_track` se suman al catálogo **de esa sesión** (mismo `id` reemplaza).
  - El perfil efectivo con el origen de cada valor (`measured`/`default` y `source`) se registra
    en el log (INFO) al abrir la sesión y tras `load`/`set_profile` (principio V).
- **Razón**: reutiliza los ejemplos del contrato como pide el usuario y fija la pista que la spec
  asume (óvalo sin cortes en tablero 3 × 2,5 m).

## R13. Batería

- **Decisión**: `battery_v = round(nominal_v − 0,25 · (|left| + |right|)/510, 3)`: voltaje nominal
  con una caída leve proporcional a la carga de los motores; sin descarga en el tiempo ni ruido.
- **Razón**: plausible (FR-016) y determinista; la spec descarta un modelo de descarga realista.

## R14. Despliegue en Railway y cliente de ejemplo

- **Decisión**:
  - `Dockerfile` sobre `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`: `uv sync --locked
    --no-dev`, copia `src/`, `contract/` (el servidor valida con los schemas) y `config/`;
    `CMD ["uv", "run", "--no-sync", "velocista-sim"]`.
  - `velocista_sim.main()` lanza uvicorn con `host 0.0.0.0` y `port = int($PORT)` (por defecto
    8000), `proxy_headers` activado (Railway termina TLS: el cliente usa `wss://`).
  - `railway.json`: builder `DOCKERFILE`, `healthcheckPath "/health"`, reinicio `ON_FAILURE`.
  - `GET /health` → 200 `{"status": "ok", "sessions": n, "max_sessions": m}` mientras haya lugar;
    503 `{"status": "full", …}` si `n ≥ VELOCISTA_MAX_SESSIONS` (por defecto 20), en cuyo caso
    `/ws` cierra las conexiones nuevas con código 1013 (try again later).
  - `examples/client.py`: script con metadatos PEP 723 (`dependencies = ["websockets>=15"]`), se
    corre sin instalar el repo con `uv run examples/client.py <url> …` (o `uv run <url-raw>`).
    Hace `set_config` → `start` → espera `--laps` vueltas o `--timeout` s → `stop` (o termina por
    `off_track`) → imprime el `summary` legible.
- **Razón**: Dockerfile da el mismo entorno local y en Railway (sin depender de la detección
  automática del builder); PEP 723 cumple SC-006 (sin clonar ni instalar el repo).
- **Alternativas**: Railpack/Nixpacks automático (menos control de versión de Python y de qué
  archivos se copian); `Procfile` (no define healthcheck).
