# Interfaz: `examples/client.py`

Cliente de ejemplo autocontenido (metadatos PEP 723, dependencia `websockets>=15`). Se ejecuta
sin instalar el repositorio:

```text
uv run examples/client.py [URL] [--kp F] [--ki F] [--kd F] [--base-speed N]
                          [--laps N] [--timeout S] [--robot ID] [--track ID]
```

| Argumento | Defecto | Significado |
|---|---|---|
| `URL` | `ws://localhost:8000/ws` | URL del WebSocket (`wss://…/ws` en Railway) |
| `--kp`, `--ki`, `--kd` | `0.045`, `0`, `0.9` | parámetros del PID |
| `--base-speed` | `180` | PWM base 0–255 |
| `--laps` | `3` | envía `stop` al recibir el `event lap` número N |
| `--timeout` | `30` | segundos máximos de corrida antes de `stop` |
| `--robot`, `--track` | — | se agregan como parámetros de conexión |

Comportamiento:

1. Conecta, espera `hello` y `config` y los muestra en una línea cada uno.
2. Envía `set_config` con los parámetros; espera el `config` de respuesta (si llega `error`, lo
   muestra y sale con código 2).
3. Envía `start`; muestra cada `event` (`run_started`, `lap`, `off_track`) en una línea.
4. Envía `stop` tras `--laps` vueltas o `--timeout` s, salvo que la corrida termine antes por
   `off_track`.
5. Al recibir `run_finished`, imprime el `summary` legible (vueltas, mejor y promedio en s,
   salidas de pista, pista, config, `config_changed`) y sale con código 0.

Errores de conexión: mensaje en español y código de salida 1. Ignora `sim_truth` y los mensajes
desconocidos (funciona igual contra el robot real, salvo que este no emite `lap`: entonces corta
por `--timeout`).
