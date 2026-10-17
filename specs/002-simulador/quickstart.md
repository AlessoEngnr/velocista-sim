# Quickstart: validar el simulador

Guía para comprobar de punta a punta que la feature funciona. Comportamiento esperado en
[contracts/ws-session.md](./contracts/ws-session.md); decisiones en [research.md](./research.md).

## Requisitos

- `uv` instalado; Python 3.12 lo provee `uv` (`.python-version`).
- Para P3: Docker (opcional, para probar la imagen) y acceso al proyecto de Railway.

```powershell
uv sync --locked
```

## 1. Tests (P1 + P2)

```powershell
uv run pytest
```

Esperado: todo en verde. Cubre, entre otros:

| Qué | Dónde | Criterio |
|---|---|---|
| Cada mensaje recibido valida contra el contrato con el último `hello` | todos los tests de `tests/integration/` | SC-002, FR-005 |
| `hello` → `config` primero; `t_ms` no decreciente; `seq` desde 0 de a 1 | `test_ws_session.py` | FR-002, FR-004, FR-007 |
| Config por defecto: ≥ 3 vueltas sin salirse en `oval-01` | `test_session_core.py`, `test_ws_session.py` | SC-001 |
| `kp = 0` → `off_track` + `run_finished` en < 10 s simulados; `oval-small` (con corte) sin `off_track` | `test_session_core.py` | SC-005 |
| Misma semilla y comandos → mismo `summary` y misma telemetría; dos corridas seguidas con la misma config → ruido distinto (sensores distintos), pero la secuencia se repite igual en otra sesión | `test_session_core.py` | SC-003 |
| Ningún rechazo cambia la sesión | `test_session_core.py`, `test_ws_sim_only.py` | SC-007 |
| Dos clientes no se afectan | `test_ws_session.py` | US1-12 |
| `world` y `robot` no se importan entre sí ni leen el reloj | `tests/unit/test_architecture.py` | Principios III y VI |
| `/health` y `examples/client.py` contra uvicorn local | `test_health_client.py` | US3 |

Prueba de tiempo real (SC-004: 5 sesiones, 10 s, desvío < 5 %), aparte porque tarda:

```powershell
uv run pytest -m slow
```

## 2. Servidor local + cliente de ejemplo

Terminal 1:

```powershell
uv run velocista-sim            # escucha en 0.0.0.0:8000 (o $env:PORT)
```

Terminal 2:

```powershell
curl http://localhost:8000/health
uv run examples/client.py ws://localhost:8000/ws --laps 3
```

Esperado:

- `/health` → `200 {"status":"ok","sessions":0,"max_sessions":20}`.
- El cliente muestra `hello` (`source sim`, `velocista-01`), `config` (`track_id oval-01`),
  `run_started`, tres `lap` de ≈ 3,4 s y el `summary` con `laps 3`, `off_tracks 0`,
  `config_changed false`.

Configuración mala:

```powershell
uv run examples/client.py ws://localhost:8000/ws --kp 0 --kd 0
```

Esperado: `off_track` (`line_lost`) en pocos segundos y `summary` con `laps 0`,
`best_lap_ms null`, `off_tracks 1`.

## 3. Comandos solo-sim (P2), a mano

Con cualquier cliente WebSocket (p. ej. `uvx --from websockets websockets ws://localhost:8000/ws`)
enviar, con la corrida detenida:

```json
{"cmd": "list"}
{"cmd": "set_profile", "measured": {"wheelbase_m": 0.128}}
{"cmd": "set_profile", "measured": {"line_sensors": 8}}
{"cmd": "load", "robot_id": "velocista-01"}
{"cmd": "load", "robot_id": "no-existe"}
{"cmd": "start"}
{"cmd": "reset"}
{"cmd": "stop"}
```

Esperado, en orden: `catalog` (`robots ["velocista-01"]`, `tracks ["oval-01"]`); `config`;
`error invalid_params` (`cmd set_profile`); `hello` + `config`; `error unknown_robot`;
`event run_started`; `error run_active` (`cmd reset`); `event run_finished`.

`load_track` con la pista de `contract/examples/valid/commands/load_track/oval-small.json`
(campo `message`) → `config` con `track_id "oval-small"`.

## 4. Imagen y despliegue (P3)

```powershell
docker build -t velocista-sim .
docker run --rm -e PORT=9000 -p 9000:9000 velocista-sim
uv run examples/client.py ws://localhost:9000/ws
```

En Railway: el servicio usa `Dockerfile` y `railway.json` (healthcheck `/health`); generar un
dominio público en *Settings → Networking*. Verificar desde otra máquina:

```powershell
curl https://<proyecto>.up.railway.app/health
uv run https://raw.githubusercontent.com/<org>/velocista-sim/main/examples/client.py wss://<proyecto>.up.railway.app/ws
```

Esperado: igual que en local (SC-006: un compañero sin el repo obtiene el `summary` en < 5 min).
