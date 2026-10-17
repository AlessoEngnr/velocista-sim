# Contrato HTTP: entrega del panel

La ruta `/` **no** forma parte del contrato v1 (igual que `/health`): es una ruta HTTP del servicio
para entregar archivos estáticos. No transporta datos de la simulación.

## Rutas

| Método | Ruta | Respuesta | Notas |
|---|---|---|---|
| `GET` | `/` | `200`, `text/html; charset=utf-8`, contenido de `static/index.html` | `StaticFiles(html=True)` |
| `GET` | `/panel.css` | `200`, `text/css` | |
| `GET` | `/js/<módulo>.js`, `/js/views/<vista>.js` | `200`, `text/javascript` | MIME forzado (research R2) |
| `GET` | ruta inexistente bajo `/` | `404` | comportamiento de `StaticFiles` |
| `GET` | `/health` | sin cambios (`specs/002-simulador/contracts/http-health.md`) | registrada **antes** del montaje |
| WS | `/ws` | sin cambios (contrato v1) | registrada **antes** del montaje |

## Garantías

- Montar el panel no cambia el comportamiento de `/health` ni de `/ws` (FR-001); los tests
  existentes de ambos siguen pasando sin modificaciones.
- La página y sus recursos no hacen pedidos a otros orígenes (sin CDN, sin fuentes externas, sin
  analítica). Los archivos estáticos no contienen ninguna URL literal `http://` ni `https://`
  (tampoco en comentarios), con la única excepción de los espacios de nombres XML que empiezan
  con `http://www.w3.org/` (p. ej. `xmlns` de SVG), que no generan pedidos. Tampoco contienen
  `ws://` ni `wss://` literales: la URL del WebSocket se arma con `location` (research R4). Un
  test (`tests/integration/test_panel_static.py`) lo verifica.
- El único pedido de datos que hace la página es el WebSocket a `/ws` del mismo origen.
- No hay autenticación (igual que `/ws`).
- Sin dependencias nuevas de ejecución: `StaticFiles` viene con Starlette/FastAPI.

## Archivos servidos

Ubicación en el repo: `src/velocista_sim/server/static/` (ver estructura en
[../plan.md](../plan.md)). Se publican con el mismo camino relativo: `static/js/state.js` →
`/js/state.js`.
