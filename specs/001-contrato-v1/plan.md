# Implementation Plan: Contrato v1 de mensajes entre velocista-sim y sus clientes

**Branch**: `001-contrato-v1` | **Date**: 2026-10-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-contrato-v1/spec.md`

## Summary

Convertir el contrato v1.1 (hoy un PDF) en una fuente de verdad versionada y verificable. Se
entregan cuatro cosas:

1. El texto del contrato en español, `contract/contract-v1.md`, en su revisión 1.2.
2. Un JSON Schema draft 2020-12 por cada mensaje, comando, perfil del robot y pista, en
   `contract/schemas/`.
3. Ejemplos válidos e inválidos con el motivo esperado del rechazo, en `contract/examples/`.
4. Un validador pequeño en `src/velocista_sim/contract/`. Combina los schemas con las reglas que
   dependen del `hello` de la sesión y la semántica de la pista. Las reglas de orden de los
   mensajes en una sesión quedan para la spec del servidor (research R8).

Los tests pytest recorren todos los ejemplos y GitHub Actions corre `uv run pytest` en cada push y
cada PR. No se implementa servidor, física ni interfaz.

## Technical Context

**Language/Version**: Python 3.12 (`.python-version`).

**Primary Dependencies**: `jsonschema` 4.26 y `referencing` 0.37, ambos ya en `uv.lock`.
`jsonschema` pasa del grupo `dev` a las dependencias de ejecución (research R1).

**Storage**: archivos JSON y Markdown versionados en `contract/`. No hay base de datos.

**Testing**: `pytest` 9 con tests parametrizados que descubren los archivos de
`contract/examples/`.

**Target Platform**: desarrollo en Windows y Linux. La CI corre en `ubuntu-latest`.

**Project Type**: biblioteca dentro de un único proyecto Python, más artefactos de contrato
independientes del lenguaje.

**Performance Goals**: no son críticos. Como referencia, validar un `telemetry` con contexto
debería tardar mucho menos que su periodo de 10 ms a 100 Hz. Así se puede usar en los tests del
servidor sin ralentizarlos.

**Constraints**:
- Sin red: los `$ref` se resuelven en memoria (R2).
- Los archivos se leen siempre en UTF-8, porque en Windows la codificación por defecto no lo es.
- Los campos desconocidos se aceptan (FR-005, R4).

**Scale/Scope**: 6 mensajes, 4 subtipos de evento, 9 comandos, perfil y pista. Unos 18 schemas y
del orden de 80 ejemplos. 3 capas de reglas, con 23 reglas no expresables en schema (19 contextuales y 4 de pista).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / regla | Evaluación | Estado |
|---|---|---|
| I. El contrato es la fuente de verdad | El contrato queda en `contract/` como texto y JSON Schema. Los cambios respecto del PDF se documentan en `contract-v1.md` (R9). Solo hay WebSocket y JSON. Las unidades no SI son las excepciones definidas en el contrato, como permite la constitución v1.1.0. | ✅ |
| II. Paridad sim–robot | Los elementos solo-sim están marcados en el texto. El validador rechaza `sim_truth` cuando `source = "robot"` y cada campo condicionado emitido sin su capacidad declarada (`odometry`, `battery_v`, `lap`), y exige esos campos cuando la capacidad sí está declarada (reglas `*_missing`). Los datos de `hello` solo cambian con `load`, que reenvía `hello`. | ✅ |
| III. El robot no conoce la pista | No aplica: no hay código del mundo ni del controlador. FR-021 (sin geometría en los mensajes salientes) queda en el texto del contrato; la verificación en el servidor corresponde a su spec. | ✅ N/A |
| IV. Control a bordo | Ningún comando del schema permite control por ciclo (FR-029). | ✅ |
| V. Perfil con defecto y medido | `robot-profile.schema.json` exige `{default, measured, source}` por parámetro. `effective_profile` calcula el valor efectivo. | ✅ |
| VI. Simulación reproducible | No aplica: no hay simulación en esta feature. | ✅ N/A |
| VII. Validación contra JSON Schema | Hay un schema por tipo de mensaje en `contract/`. Los tests validan todos los ejemplos. El validador queda disponible para validar lo que emita el servidor en specs posteriores. | ✅ |
| Restricciones técnicas | Python 3.12, `uv`, código en `src/velocista_sim/`, tests en `tests/`. `jsonschema` solo cambia de grupo, mediante `uv`, y está justificado en R1. | ✅ |
| Flujo de desarrollo | Identificadores en inglés; contrato, docs y `Violation.message` en español; Conventional Commits; los mensajes se tocan junto con contrato, schemas y tests. | ✅ |

**Resultado**: el gate se supera y no hay violaciones que justificar.

**Re-chequeo tras la fase 1**: el diseño (data-model, interfaz del validador, formato de ejemplos)
no agrega dependencias ni proyectos, y no se aparta de ningún principio. ✅

**Nota**: esta feature resuelve la sección *Pendientes* de la constitución (faltaban los JSON
Schemas). Al cerrarla, conviene una enmienda PATCH que quite ese pendiente.

## Project Structure

### Documentation (this feature)

```text
specs/001-contrato-v1/
├── spec.md
├── plan.md                  # este archivo
├── research.md              # fase 0: decisiones R1–R11
├── data-model.md            # fase 1: schemas por entidad, capas de reglas, estados
├── quickstart.md            # fase 1: cómo validar de punta a punta
├── contracts/
│   ├── validator-api.md     # interfaz pública de velocista_sim.contract
│   └── example-format.md    # formato y reglas de contract/examples/
├── checklists/requirements.md
├── review.md                # revisión del contrato por front, backend y firmware (SC-004, SC-006)
└── tasks.md                 # fase 2 (/speckit-tasks), aún no creado
```

### Source Code (repository root)

```text
contract/
├── contrato-v1.1-velocista-sim.pdf      # solo referencia histórica
├── contract-v1.md                       # texto normativo, revisión 1.2, en español
├── schemas/
│   ├── common.schema.json
│   ├── robot-profile.schema.json
│   ├── track.schema.json
│   ├── messages/
│   │   ├── hello.schema.json
│   │   ├── config.schema.json
│   │   ├── telemetry.schema.json
│   │   ├── event.schema.json
│   │   ├── catalog.schema.json
│   │   └── error.schema.json
│   └── commands/
│       ├── start.schema.json   stop.schema.json   set_config.schema.json
│       ├── set_rate.schema.json   list.schema.json   reset.schema.json
│       └── load.schema.json   set_profile.schema.json   load_track.schema.json
└── examples/
    ├── valid/<hello|config|telemetry|event|catalog|error|robot-profile|track>/*.json
    ├── valid/commands/<cmd>/*.json
    └── invalid/…                        # misma estructura, con "expected"

src/velocista_sim/
├── __init__.py
└── contract/
    ├── __init__.py          # reexporta la API pública (validator-api.md)
    ├── schemas.py           # carga de contract/schemas en un Registry (R2, R6)
    ├── result.py            # Violation, ValidationResult
    ├── validate.py          # validate_message / validate_command / validate_profile / effective_profile
    ├── context_rules.py     # capa 2: reglas que dependen de hello
    └── track_rules.py       # capa 3: semántica de pista

tests/
├── contract/
│   ├── test_schemas.py      # cada schema es válido según el metaschema 2020-12; $ref resolubles
│   ├── test_examples.py     # parametrizado sobre contract/examples (reglas 1–2 de example-format)
│   └── test_coverage.py     # SC-001, SC-005: un ejemplo por tipo y por regla
└── unit/
    ├── test_context_rules.py
    ├── test_track_rules.py
    └── test_effective_profile.py

.github/workflows/tests.yml  # push + pull_request → uv sync --locked && uv run pytest
pyproject.toml               # jsonschema en dependencies; [tool.pytest.ini_options] testpaths
```

**Structure Decision**: un solo proyecto. Los artefactos independientes del lenguaje (texto,
schemas y ejemplos) viven en `contract/`, como exige la constitución. El código Python que los
valida vive en el subpaquete `velocista_sim.contract`. Los tests se separan en `tests/contract/`,
que verifica los artefactos del contrato, y `tests/unit/`, que verifica la lógica del validador.

## Orden de implementación sugerido

1. `pyproject.toml`: mover `jsonschema` de grupo y configurar pytest. Agregar el workflow de CI
   para tener verde desde el primer commit.
2. `common.schema.json` y los schemas de los mensajes, con sus ejemplos válidos tomados del PDF
   (SC-003). Después `test_schemas.py` y `test_examples.py`.
3. Los schemas de comandos, perfil y pista, con sus ejemplos.
4. Las capas 2 y 3 del validador, con los ejemplos inválidos de cada regla y
   `test_coverage.py`.
5. `contract/contract-v1.md`: texto normativo, tabla de excepciones de unidades, marcas solo-sim y
   cambios respecto del PDF.
6. Enmienda PATCH de la constitución para retirar el pendiente de los JSON Schemas.

## Complexity Tracking

No hay violaciones de la constitución que justificar.
