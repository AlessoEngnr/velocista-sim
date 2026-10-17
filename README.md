# velocista-sim

Simulador de un robot velocista seguidor de línea. Los clientes (front, backend, optimizador) se
conectan por WebSocket y reciben JSON; el robot real (ESP32) habla el mismo contrato.

## Contrato v1

El contrato define todos los mensajes entre velocista-sim y sus clientes, y es la fuente de
verdad de la interfaz externa. Lo cumplen por igual el simulador y el robot real.

- [`contract/contract-v1.md`](contract/contract-v1.md): texto normativo (conexión, mensajes,
  comandos, perfil del robot, pista track v1 y paridad simulador–robot real).
- [`contract/schemas/`](contract/schemas/): un JSON Schema (draft 2020-12) por mensaje, comando,
  perfil y pista.
- [`contract/examples/`](contract/examples/): ejemplos válidos e inválidos; cada inválido indica
  la regla y el campo por los que se rechaza. Son también los casos de prueba.

### Validar

```powershell
uv sync --locked
uv run pytest
```

Desde Python, con el validador del paquete:

```python
from velocista_sim.contract import validate_message

result = validate_message(telemetry, hello)  # hello: el último recibido en la sesión
if not result.ok:
    for violation in result.violations:
        print(violation.rule, violation.path, violation.message)
```

También están `validate_command`, `validate_profile`, `validate_track` y `effective_profile`.
Guía paso a paso en [`specs/001-contrato-v1/quickstart.md`](specs/001-contrato-v1/quickstart.md).

## Simulador

Servidor WebSocket que se comporta como el robot según el contrato v1: una sesión independiente
por conexión, `hello` + `config` al abrirse, telemetría a `rate_hz` y los comandos generales y
solo-sim. Pista por defecto `oval-01` y perfil `velocista-01` (carpeta [`config/`](config/)).

### Servicio público

- WebSocket: `wss://velocista-sim-production.up.railway.app/ws`
- Estado: `https://velocista-sim-production.up.railway.app/health` → 200
  `{"status": "ok", "sessions": n, "max_sessions": m}`, o 503 `{"status": "full", …}` si no hay
  lugar (en ese caso `/ws` cierra las conexiones nuevas con código 1013).
- Parámetros de conexión opcionales: `?robot=<id>&track=<id>` (IDs del catálogo; `list` los
  devuelve).

### Cliente de ejemplo sin clonar el repo

[`examples/client.py`](examples/client.py) es un script con dependencias declaradas (PEP 723):
`uv` lo corre directamente desde GitHub.

```powershell
uv run https://raw.githubusercontent.com/AlessoEngnr/velocista-sim/main/examples/client.py wss://velocista-sim-production.up.railway.app/ws
uv run https://raw.githubusercontent.com/AlessoEngnr/velocista-sim/main/examples/client.py wss://velocista-sim-production.up.railway.app/ws --kp 0.05 --kd 1.0 --base-speed 200 --laps 5
```

Envía `set_config`, `start`, espera `--laps` vueltas (o `--timeout` s) y `stop`, e imprime el
`summary`. Opciones: `--kp`, `--ki`, `--kd`, `--base-speed`, `--laps` (3), `--timeout` (30),
`--robot`, `--track`. Sale con 0 si la corrida terminó, 1 ante un error de conexión y 2 si el
servidor rechazó un comando.

### En local

```powershell
uv run velocista-sim                              # sirve ws://localhost:8000/ws y /health
uv run examples/client.py ws://localhost:8000/ws  # en otra terminal
```

Variables de entorno:

| Variable | Defecto | Uso |
|---|---|---|
| `PORT` | `8000` | puerto de escucha (Railway lo asigna) |
| `VELOCISTA_SEED` | `1` | semilla base; la de cada corrida se deriva de (semilla, número de corrida) |
| `VELOCISTA_MAX_SESSIONS` | `20` | sesiones simultáneas máximas |
| `VELOCISTA_CONFIG_DIR` | `config/` del repo | carpeta con `robots/` y `tracks/` |

Con Docker: `docker build -t velocista-sim .` y
`docker run --rm -e PORT=9000 -p 9000:9000 velocista-sim`. El despliegue en Railway usa el mismo
[`Dockerfile`](Dockerfile) y [`railway.json`](railway.json) (healthcheck `/health`). Guía de
validación completa en [`specs/002-simulador/quickstart.md`](specs/002-simulador/quickstart.md).
