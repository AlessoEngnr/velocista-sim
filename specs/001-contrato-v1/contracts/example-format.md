# Formato de los ejemplos del contrato

Los ejemplos viven en `contract/examples/` y son, a la vez, documentación para los equipos y casos
de prueba (los tests los descubren automáticamente).

## Organización

```text
contract/examples/
├── valid/
│   ├── hello/            sim-default.json, robot-real.json, with-encoders-imu.json, …
│   ├── config/
│   ├── telemetry/
│   ├── event/
│   ├── catalog/
│   ├── error/
│   ├── commands/<cmd>/
│   ├── robot-profile/
│   └── track/
└── invalid/              (misma estructura)
```

Nombre de archivo: kebab-case en inglés que describe el caso (`sensor-out-of-range.json`).

## Envoltorio

```json
{
  "description": "Texto en español: qué ilustra el ejemplo",
  "hello": "sim-default",
  "message": { "type": "telemetry", "v": 1, "t_ms": 30640, "...": "..." },
  "expected": [
    { "rule": "maximum", "path": "/sensors/3" }
  ]
}
```

| Campo | Obligatorio | Significado |
|---|---|---|
| `description` | Sí | Qué ilustra o por qué es inválido, en español |
| `hello` | No | Contexto: nombre de un archivo de `valid/hello/` (sin `.json`) o un objeto `hello` en línea. Omitido = sin reglas contextuales |
| `message` | Sí | El mensaje, comando, perfil o pista tal como viaja |
| `expected` | Solo en `invalid/` | Lista no vacía de violaciones esperadas (`rule`, `path`) |

## Reglas que verifican los tests

1. Todo ejemplo de `valid/` produce `ok = True` con su contexto.
2. Todo ejemplo de `invalid/` produce exactamente las violaciones de `expected` (mismo conjunto
   de pares `rule`/`path`). Así un ejemplo inválido ilustra un solo motivo y no falla "por
   accidente" por otro.
3. Cada carpeta de primer nivel de `valid/` (y cada `commands/<cmd>/`) tiene al menos un ejemplo,
   y lo mismo en `invalid/` (SC-001).
4. Cada regla contextual de [data-model.md](../data-model.md) aparece en al menos un `expected`
   (SC-005).
5. Los ejemplos del PDF v1.1, con las correcciones de research R9, están en `valid/` con
   `description` que empieza por `"PDF v1.1:"` (SC-003).
