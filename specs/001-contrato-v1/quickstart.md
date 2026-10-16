# Quickstart: validar el contrato v1

Guía para comprobar de punta a punta que la feature funciona. Detalles de reglas en
[data-model.md](./data-model.md); interfaz del validador en
[contracts/validator-api.md](./contracts/validator-api.md); formato de ejemplos en
[contracts/example-format.md](./contracts/example-format.md).

## Requisitos

- `uv` instalado; Python 3.12 lo resuelve `uv` a partir de `.python-version`.
- Clon del repo en la rama `001-contrato-v1`.

```powershell
uv sync --locked
```

## 1. Toda la suite

```powershell
uv run pytest
```

**Esperado**: todos los tests pasan. Incluyen: schemas válidos según el metaschema 2020-12, cada
ejemplo válido aceptado, cada inválido rechazado exactamente por su `expected`, cobertura mínima
de ejemplos (SC-001, SC-005) y reglas contextuales y de pista.

## 2. Solo los ejemplos

```powershell
uv run pytest tests/contract -k examples -v
```

**Esperado**: un caso por archivo de `contract/examples/`, con el nombre del archivo en el id del
test.

## 3. Validar un mensaje a mano

```powershell
uv run python -c "import json; from pathlib import Path; from velocista_sim.contract import validate_message; ex = lambda p: json.loads(Path('contract/examples/valid', p).read_text(encoding='utf-8'))['message']; print(validate_message(ex('telemetry/pdf-robot-actual.json'), ex('hello/sim-default.json')))"
```

**Esperado**: `ValidationResult(violations=(), context_checked=True)`.

## 4. Casos de aceptación de la spec

| Escenario (spec) | Cómo verificarlo | Esperado |
|---|---|---|
| US1-2: sensor 5000 con `adc_bits = 12` | `invalid/telemetry/sensor-out-of-range.json` | `sensor_range` en `/sensors/3` (el schema solo acota a 16 bits; la cota de 12 bits es contextual) |
| US1-4: 15 sensores con hello de 16 | `invalid/telemetry/sensors-length.json` | `sensors_length` |
| US1-5: campo desconocido | `valid/telemetry/unknown-field.json` | válido |
| US2-6: `set_rate` 150 | `invalid/commands/set_rate/hz-too-high.json` | `maximum` en `/hz` |
| US3-2: pista con 1 punto | `invalid/track/centerline-too-short.json` | `minItems` en `/centerline` |
| US4-1: `sim_truth` con robot real | `invalid/telemetry/sim-truth-robot.json` | `sim_truth_without_sim` |
| US4-2: `odometry` sin encoders ni IMU | `invalid/telemetry/odometry-without-capability.json` | `odometry_without_capability` |
| US4-5: `lap` sin `lap_timing` | `invalid/telemetry/lap-without-timing.json` | `lap_without_timing` |
| US4-6: encoders declarados sin `odometry` | `invalid/telemetry/odometry-missing.json` | `odometry_missing` |
| US3-5: `set_profile` de un parámetro de `hello` | `invalid/commands/set_profile/change-line-sensors.json` | `enum` en `/measured` |

Los escenarios de US2 y US3 que requieren un servidor (secuencias `start`/`stop`, `load_track`
aceptado, orden de los mensajes) no se verifican en esta feature: aquí solo se validan los
mensajes de esas secuencias uno a uno. El comportamiento y el orden quedan para la spec del
servidor.

## 5. Integración continua

Hacer push de la rama y abrir un PR: el workflow `tests` debe ejecutar `uv sync --locked` y
`uv run pytest` y quedar en verde.
