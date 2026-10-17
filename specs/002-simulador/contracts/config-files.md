# Interfaz: archivos de catálogo y variables de entorno

## `config/robots/<id>.json`

- Contenido: un perfil del robot con la forma de `contract/schemas/robot-profile.schema.json`
  (sin envoltorio de ejemplo: el objeto del perfil directamente).
- El nombre del archivo (sin `.json`) MUST ser igual a `id.default`.
- Restricciones del simulador v1: `motors = 2`; `encoders`, `imu` y `turbine` efectivos en
  `false` (no se simulan).
- `velocista-01.json` es copia exacta del `message` de
  `contract/examples/valid/robot-profile/velocista-01-default.json`; un test verifica que no
  diverjan.

## `config/tracks/<id>.json`

- Contenido: una pista track v1 (`contract/schemas/track.schema.json` + reglas de pista).
- El nombre del archivo MUST ser igual a `id`.
- `oval-01.json`: estadio cerrado en tablero 3,00 × 2,50 m, centro (1,50; 1,25), rectas de
  1,50 m, radio 0,60 m, puntos cada ≈ 5 mm, `line_width` 0,019, `gaps: []`, `start.at` 0,10,
  `rules_profile` `"lgr2026"`.

Al arrancar, el servidor valida todos los archivos con `velocista_sim.contract` y no arranca si
alguno falla (mensaje en español con archivo, regla y path).

## Variables de entorno

| Variable | Defecto | Uso |
|---|---|---|
| `PORT` | `8000` | puerto de escucha (Railway lo asigna) |
| `VELOCISTA_SEED` | `1` | semilla base de todas las sesiones; la de cada corrida se deriva de (base, número de corrida) |
| `VELOCISTA_MAX_SESSIONS` | `20` | sesiones simultáneas máximas |
| `VELOCISTA_CONFIG_DIR` | `config/` del repo | carpeta con `robots/` y `tracks/` |
