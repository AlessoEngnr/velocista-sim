# Implementation Plan: Simulador de velocista accesible por WebSocket (contrato v1)

**Branch**: `002-simulador` | **Date**: 2026-10-16 | **Spec**: [spec.md](./spec.md)

**Input**: Especificación de la feature en `specs/002-simulador/spec.md`

## Summary

Servicio WebSocket (`/ws`) que se comporta como el robot velocista según el contrato v1: una
sesión independiente por conexión, con `hello` + `config` al abrirse, telemetría a `rate_hz`,
eventos de corrida y los comandos generales y solo-sim. La simulación es un núcleo síncrono y
determinista que avanza por pasos fijos de `dt = 2 ms` sin leer el reloj; un adaptador asyncio
(FastAPI + uvicorn) solo decide **cuándo** ejecutar cada paso para ir en tiempo real. El mundo
(pista, física diferencial con motores de primer orden y límite de agarre, regleta de 16 sensores
con ruido sembrado) y el robot (posición de línea + PID a bordo) son paquetes separados que solo
se comunican por lecturas ADC y PWM. Pista por defecto `oval-01` y perfil `velocista-01` en
`config/`; despliegue en Railway con Dockerfile, escuchando en `PORT`, con `/health`.

## Technical Context

**Language/Version**: Python 3.12 (`.python-version`)

**Primary Dependencies**: FastAPI + uvicorn[standard] (ya presentes: WebSocket `/ws` y `/health`),
jsonschema (validador del contrato, ya presente), **numpy** (nueva: lecturas vectorizadas de la
regleta; ver research R3). Dev: pytest, **httpx** (nueva: la necesita `fastapi.testclient`),
**websockets** (explícita en dev: cliente de ejemplo y tests de extremo a extremo; hoy solo llega
transitiva por uvicorn[standard]).

**Storage**: archivos JSON de solo lectura en `config/robots/` y `config/tracks/`; estado de sesión
en memoria, sin persistencia.

**Testing**: pytest; `fastapi.testclient.TestClient` para el WebSocket con reloj acelerado
inyectado; núcleo de sesión probado sin E/S; todo mensaje recibido se valida con
`velocista_sim.contract.validate_message` contra el último `hello` (research R10). La prueba de
tiempo real (SC-004) lleva el marcador `slow`, excluido por defecto (`addopts = "-m 'not slow'"`)
y ejecutado en CI como paso aparte (`uv run pytest -m slow`).

**Target Platform**: contenedor Linux en Railway (Dockerfile con imagen oficial de uv y Python
3.12); desarrollo local en Windows/Linux.

**Project Type**: web-service (servidor WebSocket) + librería interna de simulación.

**Performance Goals**: tiempo real a 500 pasos/s por sesión; núcleo ≥ 10.000 pasos/s por sesión en
un núcleo de desarrollo (≥ 20× tiempo real); telemetría con desvío promedio < 5 % en 10 s con 5
sesiones (SC-004).

**Constraints**: simulación sin reloj ni RNG global (principio VI); el módulo robot no importa el
mundo (principio III); cliente lento no frena la simulación ni otras sesiones (descarte solo de
`telemetry`); ningún mensaje lleva geometría de pista.

**Scale/Scope**: 5–10 sesiones simultáneas (equipo del curso); máximo configurable 20.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Cómo se cumple | Estado |
|---|---|---|
| I. Contrato fuente de verdad | No se agrega ni cambia ningún mensaje, campo, comando ni código de error. Los comandos entrantes se validan con `validate_command` y el `code` del `error` se deriva de la regla violada según la tabla del contrato (research R8). `reset` no tiene respuesta porque el contrato no le asigna una. Unidades: las del contrato (ms, ADC, milésimas, PWM; resto SI). | ✅ |
| II. Paridad sim–robot | Solo se usan los elementos solo-sim del contrato (`sim_truth`, `reset`, `load`, `set_profile`, `load_track`). `hello` declara `encoders = imu = turbine = false`, así nunca se emite `odometry`; los perfiles del catálogo que declaren encoders/IMU/turbina se rechazan al arrancar (R12). | ✅ |
| III. El robot no conoce la pista | Paquetes `velocista_sim.world` y `velocista_sim.robot` sin imports cruzados; el robot recibe solo `sensors` (lista de enteros ADC) y su configuración/calibración propia. Un test con `ast` lo verifica (R2). La verdad del mundo solo sale en `sim_truth`. | ✅ |
| IV. Control a bordo | El PID corre dentro de la simulación cada `control_period_ms`; ningún comando fija PWM. | ✅ |
| V. Perfil default/measured | Se usa siempre `effective_profile`; `set_profile` fija/borra `measured`. El perfil efectivo con el origen de cada valor se **registra** en el log del servidor al abrir la sesión y tras cada `load`/`set_profile` (R12). | ✅ |
| VI. Simulación reproducible | Paso fijo `dt = 2 ms`; `t_ms` es tiempo simulado; el reloj solo lo lee el `Pacer` del servidor; comandos aplicados al inicio de un paso; ruido con un `numpy.random.Generator` nuevo en cada `start`, sembrado con (semilla base de la sesión, número de corrida) vía `SeedSequence`: cada corrida tiene ruido distinto y la secuencia completa es reproducible (R5, R6). Test de reproducibilidad (SC-003) y test que prohíbe `time`/`random`/`datetime` en `world` y `robot`. | ✅ |
| VII. Validación contra JSON Schema | Todo mensaje emitido en los tests pasa por `validate_message` con el último `hello`; un helper de test falla ante cualquier violación (R10). | ✅ |
| Restricciones técnicas | Python 3.12, `uv add` para numpy/httpx/websockets (justificadas arriba), código en `src/velocista_sim/`, tests en `tests/`. | ✅ |
| Flujo de desarrollo | Identificadores en inglés; docstrings, comentarios y `error.message` en español; Conventional Commits. | ✅ |

Sin violaciones: no hace falta Complexity Tracking.

**Re-check post-diseño (Phase 1)**: el diseño de [data-model.md](./data-model.md) y
[contracts/](./contracts/) mantiene los nueve puntos. Observaciones: (a) el robot recibe
`adc_white`/`adc_black` como **calibración propia** (el robot real también los conoce por
calibración), no como estado del mundo; (b) el reloj acelerado de los tests es inyección interna
del `Pacer` y no cambia ningún paso ni ningún `t_ms`, por lo que no es un "modo batch" para
clientes (fuera de alcance) ni rompe el principio VI.

## Project Structure

### Documentation (this feature)

```text
specs/002-simulador/
├── plan.md              # Este archivo
├── research.md          # Phase 0: decisiones técnicas (R1–R14)
├── data-model.md        # Phase 1: entidades, estados y orden de un paso
├── quickstart.md        # Phase 1: guía de validación de extremo a extremo
├── contracts/
│   ├── ws-session.md    # Comportamiento del servidor sobre el contrato v1 (orden, errores, tiempos)
│   ├── http-health.md   # GET /health
│   ├── world-robot.md   # Interfaz interna mundo ↔ robot ↔ sesión
│   ├── config-files.md  # Formato de config/robots y config/tracks, variables de entorno
│   └── client-cli.md    # Uso de examples/client.py
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks; no lo crea este comando)
```

### Source Code (repository root)

```text
src/velocista_sim/
├── __init__.py              # main(): uvicorn en 0.0.0.0:$PORT (por defecto 8000)
├── contract/                # (existente) validador del contrato v1
├── world/                   # Mundo: pista y física; NO importa robot ni server
│   ├── __init__.py
│   ├── params.py            # WorldParams (desde el perfil efectivo)
│   ├── track.py             # TrackGeometry: tramos con tinta, longitud, proyección, grilla espacial
│   ├── sensors.py           # Lecturas ADC de la regleta (cobertura + ruido sembrado)
│   ├── physics.py           # Tracción diferencial, motores 1er orden, límite lateral
│   └── world.py             # World: reset_to_start, set_motor_pwm, read_sensors, step, truth, detección
├── robot/                   # Robot a bordo; NO importa world ni server
│   ├── __init__.py
│   ├── params.py            # RobotParams (sensores, calibración, periodo de control)
│   ├── line.py              # line_position, line_lost, error
│   ├── pid.py               # PID discreto por paso de control
│   └── robot.py             # Robot.tick(sensors) -> salida de control y PWM
└── server/                  # Sesiones y transporte; único que conoce world y robot
    ├── __init__.py
    ├── settings.py          # Settings desde entorno (PORT, VELOCISTA_SEED, …)
    ├── catalog.py           # Carga y valida config/robots y config/tracks
    ├── commands.py          # Parseo de frames y mapeo de violaciones a códigos de error
    ├── session.py           # Session: núcleo síncrono (pasos, comandos, corrida, mensajes)
    ├── pacer.py             # Ritmo en tiempo real con asyncio + cola de salida con descarte
    └── app.py               # create_app(): FastAPI, /ws y /health

config/
├── robots/velocista-01.json # Perfil (copia del ejemplo velocista-01-default del contrato)
└── tracks/oval-01.json      # Pista por defecto track v1 (estadio, sin cortes)

examples/
└── client.py                # Cliente de ejemplo (script PEP 723 con dependencia websockets)

tests/
├── conftest.py              # (existente) + fixtures de sesión y cliente validador
├── support/
│   └── contract_client.py   # Envoltorio de TestClient que valida cada mensaje recibido
├── unit/
│   ├── test_world_*.py      # pista, sensores, física, vueltas, salida de pista
│   ├── test_robot_*.py      # línea y PID
│   ├── test_commands.py     # mapeo de errores
│   └── test_architecture.py # imports prohibidos (world↔robot, reloj, RNG global)
├── integration/
│   ├── test_session_core.py # núcleo sin E/S: corridas, determinismo SC-003, SC-005, SC-007
│   ├── test_ws_session.py   # TestClient: US1 (P1)
│   ├── test_ws_sim_only.py  # TestClient: US2 (P2)
│   └── test_health_client.py# /health y examples/client.py contra uvicorn local (US3)
└── slow/
    └── test_realtime_rate.py# SC-004 (marcador slow)

Dockerfile                   # imagen uv + Python 3.12; CMD velocista-sim
.dockerignore
railway.json                 # healthcheckPath /health
```

**Structure Decision**: proyecto único en `src/velocista_sim/` con los tres paquetes pedidos
(`world`, `robot`, `server`) junto al `contract` existente. `server.session` es un núcleo sin E/S
(se prueba en milisegundos y de forma determinista); `server.pacer` y `server.app` son el único
código que toca asyncio y el reloj. La configuración de catálogo vive fuera del paquete, en
`config/`, igual que `contract/schemas/` (se localiza subiendo desde el módulo, como en el
validador, o con `VELOCISTA_CONFIG_DIR`).

## Complexity Tracking

No aplica: el Constitution Check no tiene violaciones.
