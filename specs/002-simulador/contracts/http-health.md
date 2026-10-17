# Interfaz: `GET /health`

Endpoint HTTP para el healthcheck de Railway (`railway.json` → `healthcheckPath: "/health"`).
No forma parte del contrato v1 (que solo define el WebSocket), igual que cualquier ruta de
infraestructura; no transporta mensajes del robot.

| Situación | Código | Cuerpo (JSON) |
|---|---|---|
| Puede aceptar sesiones | 200 | `{"status": "ok", "sessions": 3, "max_sessions": 20}` |
| Lleno (`sessions ≥ max_sessions`) | 503 | `{"status": "full", "sessions": 20, "max_sessions": 20}` |

- Sin parámetros ni autenticación; no lee el estado de ninguna sesión más allá del conteo.
- Responde en < 50 ms (no espera a la simulación).
- `HEAD /health` no es necesario.
