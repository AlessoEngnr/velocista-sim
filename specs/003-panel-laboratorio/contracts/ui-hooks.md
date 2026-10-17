# Contrato de la interfaz: distribución y anclas para los tests

Fija la estructura de la página que usan los tests de navegador y quien lea el código. Los
atributos `data-testid` son estables; las clases CSS no lo son.

## Distribución (FR-038)

```text
┌ header.topbar ───────────────────────────────────────────────────────────────────────────┐
│ marca · [conn-status] · [run-status][run-id] [lap-n]/[lap-target] [lap-current] [battery] │
│ [rate-hz] [track-id] [seq] [seq-lost]                              [robot-id] [source]   │
├ col izquierda ─────────┬ col central (más ancha) ─────────────┬ col derecha ─────────────┤
│ card Regleta           │ card Rastro                          │ card Control             │
│  [sensors-canvas]      │  [trail-canvas] [btn-trail-clear]    │  [btn-start][btn-stop]   │
│  [line-position]       │  franja: [speed] [distance]          │  [btn-reset] [lap-target-input]
│  [error] [line-lost]   │          [pose-x] [pose-y] [theta]   │  pestañas: [tab-tuning]  │
│ card Controlador       │                                      │   [tab-robot-track]      │
│  [pid-p][pid-i][pid-d] │                                      │   [tab-calibration]      │
│  [pid-out]             │                                      │ card Vueltas             │
│ card Motores           │                                      │  [lap-last][lap-best]    │
│  [pwm-left][pwm-right] │                                      │  [lap-avg] [lap-history] │
│ card Registro [log]    │                                      │ card Corridas [summaries]│
└────────────────────────┴──────────────────────────────────────┴──────────────────────────┘
```

- Grilla CSS de tres columnas (`minmax(280px, 1fr) minmax(0, 2fr) minmax(320px, 1.2fr)`),
  altura `100vh` en ≥ 1440 × 900 sin desplazamiento de página; las tarjetas con listas largas
  desplazan por dentro (FR-044).
- Por debajo de ~1100 px de ancho: una columna, en orden Control → izquierda → centro (`order`),
  sin desplazamiento horizontal.
- Datos de sesión (`session_id`, capacidades, `firmware`, `hw_rev`) en un `<details>` plegado
  dentro del selector de robot de la barra superior (FR-039).
- Con `source = "robot"`: se ocultan [btn-reset], [tab-robot-track], [tab-calibration] y la card
  Rastro (la columna central muestra un aviso de que no hay `sim_truth`). Sin batería: se oculta
  [battery]. Sin `lap_timing`: se ocultan vueltas, [lap-target-input] y la card Vueltas.

## Anclas `data-testid`

| `data-testid` | Contenido / uso |
|---|---|
| `conn-status` | texto `CONECTANDO`, `CONECTADO` o `DESCONECTADO`, con atributo `data-state` = `connecting`/`open`/`closed` |
| `btn-reconnect` | visible solo con `closed` |
| `run-status` | `SIN CORRIDA` / `EN CORRIDA`, `data-state` = `idle`/`running` |
| `run-id`, `lap-n`, `lap-target`, `lap-current`, `battery`, `rate-hz`, `track-id` | valores de la barra superior |
| `seq`, `seq-lost` | último `seq` y telemetrías perdidas |
| `robot-id`, `source`, `session-id` | datos de `hello` |
| `sensors-canvas`, `trail-canvas` | canvas; `data-points` en el del rastro = puntos guardados |
| `line-position`, `error`, `line-lost` | regleta |
| `pid-p`, `pid-i`, `pid-d`, `pid-out`, `pwm-left`, `pwm-right` | controlador y motores |
| `speed`, `distance`, `pose-x`, `pose-y`, `theta` | franja del rastro |
| `btn-trail-clear` | Limpiar rastro (acción local, no envía comandos) |
| `btn-start`, `btn-stop`, `btn-reset` | control de corridas |
| `lap-target-input` | vueltas objetivo |
| `kp-range`, `kp-input`, `ki-range`, `ki-input`, `kd-range`, `kd-input`, `base-speed-range`, `base-speed-input`, `rate-input` | ajuste del controlador |
| `tab-tuning`, `tab-robot-track`, `tab-calibration` | pestañas (control segmentado), `aria-selected` |
| `robot-select`, `track-select`, `btn-catalog-refresh`, `track-file` | robot y pista |
| `calib-<key>` (`calib-wheelbase_m`, …), `calib-<key>-state`, `btn-calib-apply`, `btn-calib-clear-<key>` | calibración |
| `lap-last`, `lap-best`, `lap-avg`, `lap-history` | vueltas |
| `summaries` | lista de resúmenes (`li` por corrida, `data-run-id`) |
| `log` | registro (`li` con `data-kind` = `event`/`error`/`local`/`warning`) |

## Accesibilidad mínima

- Botones y campos con `<label>` asociado; las pestañas usan `role="tablist"`/`role="tab"`.
- `conn-status`, `run-status` y `line-lost` tienen `aria-live="polite"`; los valores que cambian
  a 100 Hz **no** (sería ruido para un lector de pantalla).
- Ningún estado se comunica solo con color (FR-042, SC-011).
