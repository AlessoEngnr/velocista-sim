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
