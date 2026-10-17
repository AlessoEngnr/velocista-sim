# Fase 0 — Investigación y decisiones: Contrato v1

**Feature**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Fecha**: 2026-10-16

El contexto técnico no dejó incógnitas abiertas: el usuario fijó stack, ubicación de archivos y
alcance. Esta fase registra las decisiones de diseño que el plan necesita y que no estaban dadas.

---

## R1. Dependencia `jsonschema`: de desarrollo a ejecución

- **Decisión**: mover `jsonschema` del grupo `dev` a las dependencias de ejecución con
  `uv remove --dev jsonschema` + `uv add jsonschema`.
- **Razón**: el validador contextual vive en `src/velocista_sim/contract/` (código del paquete) y
  usa `jsonschema` para la parte estructural. Si queda solo en `dev`, el paquete instalado sin el
  grupo de desarrollo falla al importar el módulo. Además, el servidor de specs posteriores podrá
  usar el mismo validador en sus tests y, si se decide, en modo depuración.
- **Justificación ante la constitución** (Restricciones técnicas: "nuevas dependencias MUST
  justificarse"): no es una dependencia nueva, ya está en `uv.lock` (4.26.0 + `referencing`
  0.37.0); solo cambia de grupo.
- **Alternativas**: (a) dejarla en `dev` e importarla de forma diferida: frágil, el módulo sería
  inutilizable fuera de tests; (b) validar a mano sin `jsonschema`: duplicaría lo que el schema ya
  expresa y rompería el principio VII.

## R2. Draft y resolución de referencias entre schemas

- **Decisión**: todos los schemas declaran `"$schema": "https://json-schema.org/draft/2020-12/schema"`
  y un `$id` absoluto con base `https://velocista-sim.local/contract/v1/` (p. ej.
  `.../messages/telemetry.schema.json`). Las piezas comunes van en `common.schema.json` (`$defs`)
  y se referencian con `$ref` relativo (`../common.schema.json#/$defs/pwm`). El validador carga
  todos los archivos de `contract/schemas/` en un `referencing.Registry` y usa
  `Draft202012Validator` con `format_checker`.
- **Razón**: `$id` absolutos permiten resolver `$ref` sin red ni rutas del sistema de archivos; el
  dominio `.local` deja claro que no es una URL publicada. `referencing` es la API vigente de
  `jsonschema` ≥ 4.18 (`RefResolver` está deprecado).
- **Alternativas**: un único schema monolítico con `oneOf` por `type`: peores mensajes de error
  (jsonschema reporta fallos de todas las ramas) y contradice "un schema por mensaje".

## R3. Selección del schema: despacho por `type`/`cmd` en el validador

- **Decisión**: no hay schema "unión". El validador lee `type` (mensajes) o `cmd` (comandos) y
  aplica el schema correspondiente; si el discriminador falta o es desconocido, informa la regla
  `unknown_type` / `unknown_cmd`. `event` es un único schema con `$defs` por subtipo y
  `if`/`then` sobre `event` (un `const` por rama) para que el error apunte al subtipo correcto.
- **Razón**: errores precisos y una sola fuente de verdad por mensaje.
- **Alternativas**: un schema por subtipo de evento (4 archivos): más archivos sin ganancia; el
  usuario pidió un schema por mensaje.

## R4. Campos desconocidos

- **Decisión**: `additionalProperties` no se restringe (queda `true`) en mensajes, comandos,
  perfil y pista. Los objetos anidados con forma cerrada en v1 (`motors`, `sim_truth`,
  `odometry`, `capabilities`) tampoco se cierran.
- **Razón**: FR-005 — agregar campos no rompe clientes y no sube `v`.
- **Consecuencia aceptada**: un campo mal escrito (`seqq`) no se detecta como "sobrante", pero sí
  como "falta `seq`" si es obligatorio. Para opcionales mal escritos no hay detección; se
  documenta en `contract-v1.md`.

## R5. Reparto de reglas: schema vs. validador contextual

- **Decisión**: el schema expresa todo lo que no depende de otro mensaje; el validador contextual
  (con el `hello` de la sesión) expresa el resto. Además hay reglas semánticas de pista que JSON
  Schema no puede expresar (geometría) y que no dependen de `hello`. Ver la tabla completa en
  [data-model.md § Reglas](./data-model.md#reglas-de-validación).
- **Dentro del schema** (sin contexto): tipos, `required`, enums, rangos fijos (PWM −255…255,
  `rate_hz` 10–100, `kp ≥ 0`), sensores en 0…65535 (cota de 16 bits), `run_id` obligatorio si y
  solo si `running = true` (`if`/`then`/`else`), `set_config` con al menos un campo
  (`anyOf` de `required`), forma del perfil `{default, measured, source}`.
- **Validador contextual** (necesita `hello`): longitud de `sensors`, cota `2^adc_bits − 1`, cota
  superior de `line_position`, `error = line_position − centro`, presencia obligatoria o prohibida
  de `odometry` y sus campos según `encoders`/`imu`, de `battery_v` según `voltage_sense`, de
  `sim_truth` según `source` y del bloque `lap` según `lap_timing` y `running`, más `event lap` y
  `summary.laps…` según `lap_timing`. El contexto es el último `hello` de la sesión (cambia tras
  `load`).
- **Semántica de pista** (sin contexto): `at` ≤ longitud de `centerline`, puntos dentro de
  `board`, `gaps` sin superposición, muestreo ≈ 0,005 m.
- **Razón**: el usuario pidió explícitamente un validador contextual pequeño; mantener en el
  schema todo lo posible deja a otros lenguajes (front en JS, firmware) reutilizarlo.

## R6. Ubicación de los schemas en tiempo de ejecución

- **Decisión**: los schemas viven solo en `contract/schemas/` (fuera del paquete). El validador
  recibe la carpeta como parámetro opcional; por defecto la busca en `contract/schemas` subiendo
  desde el archivo del módulo hasta la raíz del repo.
- **Razón**: la constitución exige que el contrato viva en `contract/`; copiar los schemas dentro
  del paquete crearía dos fuentes. El proyecto se ejecuta desde el repo (`uv run`, instalación
  editable), por lo que la búsqueda relativa funciona.
- **Alternativas**: incluirlos como datos del paquete al construir la rueda: se reevaluará cuando
  exista despliegue (spec del servidor).

## R7. Formato de los archivos de ejemplo

- **Decisión**: cada ejemplo es un JSON envoltorio:

  ```json
  {"description": "…", "hello": "<nombre de ejemplo válido de hello> | {…} | omitido",
   "message": {…},
   "expected": [{"rule": "maximum", "path": "/sensors/3"}]}
  ```

  `expected` existe solo en `invalid/`. `rule` es la palabra clave de JSON Schema que falla
  (`required`, `maximum`, `type`, `enum`, …) o el identificador de regla contextual
  (`sensors_length`, `sim_truth_without_sim`, …); `path` es el JSON Pointer dentro de `message`.
  Organización: `contract/examples/{valid,invalid}/<schema>/<caso>.json`. Formato detallado en
  [contracts/example-format.md](./contracts/example-format.md).
- **Razón**: JSON no admite comentarios; el envoltorio documenta el motivo de forma verificable
  (los tests comparan `rule` y `path`, no el texto). Referenciar el `hello` por nombre evita
  repetirlo en cada ejemplo de telemetría.
- **Alternativas**: archivo `README` por carpeta con los motivos: no verificable; JSON Lines:
  incómodo de leer y editar.

## R8. Reglas de secuencia (orden y monotonía)

- **Decisión** (revisada al aprobar el plan, 2026-10-16): las reglas de secuencia —`hello`
  primero y `config` segundo (FR-008), `t_ms` no decreciente (FR-010), `seq` desde 0 y sin saltos
  (FR-018), un solo `run_finished` por `run_id` e inmediatamente tras `off_track` (FR-025)— **no**
  se implementan en esta feature. Quedan para la spec del servidor, que tendrá secuencias reales
  que verificar.
- **Razón**: mantener el validador pequeño, como se pidió; sin servidor no hay secuencias reales
  que validar.
- **Alternativa descartada**: un `SessionValidator` en este módulo, propuesto en la primera
  versión del plan.

## R9. Versión del documento vs. versión del protocolo

- **Decisión**: el protocolo sigue en `v = 1`. El documento `contract/contract-v1.md` lleva su
  propia revisión **1.2** (el PDF era el borrador 1.1) y una sección de cambios respecto del PDF:
  `capabilities.lap_timing`, `capabilities.battery.voltage_sense`, `error.code`, `error.cmd`,
  `summary.config_changed`, forma unificada de `summary.config`, `v` obligatorio en `event` y, tras
  los análisis del 2026-10-16: `hello` reenviado tras `load` (único comando que cambia datos de
  `hello`), `set_profile` limitado a parámetros físicos y de calibración, `capabilities.motors` fijo
  en 2, valores de `source` del perfil en inglés (el PDF usaba `"estimado"`), campos condicionados
  obligatorios cuando su capacidad está declarada, `summary.laps` no nulo con `lap_timing = true` y
  `best_lap_ms`/`avg_lap_ms` coherentes con `laps`, origen de coordenadas de la pista y tolerancia
  de muestreo de ±10 %.
- **Razón**: los cambios son aditivos o restringen casos que el PDF no definía, excepto
  `summary.config`, `v` en `event` y los valores de `source`; como el PDF
  era borrador y no hay implementaciones, se consideran correcciones del borrador, no ruptura.

## R10. Integración continua

- **Decisión**: `.github/workflows/tests.yml`, disparado en `push` y `pull_request`, en
  `ubuntu-latest`: `actions/checkout@v5`, `astral-sh/setup-uv@v6` (con caché), `uv sync --locked`
  y `uv run pytest`. La versión de Python sale de `.python-version` (3.12).
- **Razón**: la constitución exige que `uv run pytest` pase antes de integrar en `main`;
  `--locked` falla si `uv.lock` no está al día, lo que detecta dependencias agregadas sin `uv add`.
- **Alternativas**: matriz de varias versiones de Python: innecesaria, el proyecto fija 3.12.

## R11. Configuración de pytest

- **Decisión**: `[tool.pytest.ini_options]` en `pyproject.toml` con `testpaths = ["tests"]`; los
  tests de ejemplos se parametrizan descubriendo los archivos de `contract/examples/`, de modo que
  agregar un ejemplo agrega un caso sin tocar código.
