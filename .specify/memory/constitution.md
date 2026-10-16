# Constitución de velocista-sim

## Principios

### I. El contrato es la fuente de verdad

- El contrato en `contract/` define toda la interfaz externa del sistema y prevalece sobre el
  código, la documentación y cualquier otra fuente.
- El único transporte permitido es WebSocket; todos los mensajes son JSON.
- Toda magnitud física en los mensajes MUST expresarse en unidades SI (m, s, rad, m/s, rad/s, …),
  salvo las excepciones definidas explícitamente como tales en el contrato, con su unidad y rango
  (en v1: tiempo en ms, lecturas de sensores en cuentas ADC crudas, `line_position` en milésimas
  de sensor y PWM de motores en −255…255). Una unidad no SI que no figure como excepción en el
  contrato está prohibida.
- Ningún mensaje, campo o comando puede añadirse, modificarse o eliminarse en el código sin antes
  actualizar el contrato (texto y JSON Schema) en un commit previo o en el mismo cambio.

**Razón**: el simulador y el robot real deben ser intercambiables para los clientes; eso solo es
posible si ambos obedecen un único contrato explícito.

### II. Paridad simulador–robot real

- Un cliente conectado al simulador MUST observar los mismos tipos de mensaje, con la misma
  semántica y las mismas unidades, que conectado al robot real.
- Los campos opcionales dependen de lo que el robot declara en `hello.capabilities`
  (p. ej. `odometry` solo si tiene encoders o IMU; `battery_v` solo si mide voltaje). Que un
  campo opcional falte porque la capacidad no está declarada no viola la paridad; emitirlo sin
  declarar la capacidad, sí.
- Las únicas diferencias permitidas son los campos y comandos marcados como **solo-sim** en el
  contrato: `sim_truth`, `reset`, `load`, `set_profile` y `load_track`.
- Todo nuevo elemento solo-sim MUST quedar marcado explícitamente como tal en el contrato.
- Un cliente MUST poder funcionar correctamente ignorando por completo los elementos solo-sim.

**Razón**: el simulador existe para desarrollar y probar clientes y controladores que luego se
usan sin cambios con el robot físico.

### III. El robot no conoce la pista

- El **mundo** (pista y física) y el **robot** (sensores y controlador) MUST ser módulos
  separados, sin importaciones del mundo hacia el controlador.
- El controlador MUST recibir únicamente lecturas de sensores (y su configuración); nunca la
  geometría de la pista, la pose verdadera ni ningún otro estado del mundo.
- La verdad del mundo solo puede salir hacia los clientes a través de campos solo-sim
  (`sim_truth`), nunca hacia el controlador.

**Razón**: un controlador que "ve" la pista daría resultados imposibles de reproducir en el robot
real y anularía el valor del simulador.

### IV. Control a bordo; los clientes configuran y observan

- El lazo de control MUST ejecutarse a bordo (en el robot o en su equivalente simulado).
- Los clientes MUST limitarse a configurar parámetros y observar telemetría; ningún comando del
  contrato puede actuar como lazo de control remoto (p. ej. fijar velocidades de motor por ciclo).

**Razón**: la latencia y la pérdida de conexión de una red real no deben afectar la estabilidad
del robot; el simulador reproduce esa arquitectura.

### V. Perfil del robot: valor por defecto y valor medido

- Cada parámetro del perfil del robot MUST declarar un valor por defecto y admitir un valor
  medido opcional.
- Cuando existe valor medido, este MUST prevalecer sobre el valor por defecto.
- El perfil efectivo (con el origen de cada valor) MUST poder consultarse o registrarse.

**Razón**: el simulador debe funcionar desde el primer día con valores razonables y converger
hacia el robot físico a medida que se miden sus parámetros.

### VI. Simulación reproducible

- Con la misma semilla, la misma configuración (perfil, pista, parámetros) y los mismos comandos
  aplicados en los mismos pasos, la simulación MUST producir exactamente los mismos resultados.
- La simulación MUST avanzar solo por pasos fijos de `dt` y nunca leer el reloj del sistema.
- El ritmo en tiempo real lo marca el servidor con el reloj del sistema, decidiendo cuándo
  ejecutar cada paso; ese ritmo no altera el resultado de los pasos.
- Los comandos recibidos MUST aplicarse al inicio de un paso de simulación, nunca a mitad de uno.
- Toda fuente de aleatoriedad (ruido de sensores, perturbaciones) MUST derivarse de la semilla
  configurada; queda prohibido usar RNG globales dentro de la simulación.

**Razón**: sin reproducibilidad no es posible depurar, comparar controladores ni escribir tests
fiables.

### VII. Validación de mensajes contra JSON Schema

- Cada tipo de mensaje del contrato MUST tener su JSON Schema en `contract/`.
- Los tests MUST validar contra su schema todo mensaje que el sistema emite.
- Un mensaje que no valida es un defecto bloqueante, aunque el cliente lo tolere.

**Razón**: la validación automática es la única forma de garantizar que el principio I se cumple
en la práctica.

## Restricciones técnicas

- Lenguaje: Python 3.12.
- Gestión de dependencias y entorno: `uv` (no se usa `pip` ni `requirements.txt` directamente).
- Código fuente en `src/velocista_sim/`.
- Tests con `pytest` en `tests/`.
- Nuevas dependencias MUST justificarse y añadirse mediante `uv add`.

## Flujo de desarrollo

- Idioma del código: todo identificador MUST estar en inglés: nombres de paquetes y módulos,
  archivos `.py`, clases, funciones, métodos, variables y constantes.
- Idioma del contrato: los nombres de mensajes, campos y comandos del contrato MUST estar en
  inglés (p. ej. `sim_truth`, `set_profile`, `load_track`).
- Idioma de todo lo demás: specs, planes, tareas, contrato (texto descriptivo), README,
  docstrings, comentarios y mensajes de error dirigidos al usuario MUST redactarse en español.
- Los commits MUST seguir Conventional Commits con el tipo en inglés (`feat`, `fix`, `docs`,
  `test`, `build`, `chore`, `refactor`, …), alcance opcional en inglés y descripción en español
  (p. ej. `docs(contract): agrega borrador del contrato v1.1`).
- Un cambio que toca mensajes MUST incluir: actualización del contrato, de sus JSON Schemas y de
  los tests de validación correspondientes.
- Los tests MUST pasar (`uv run pytest`) antes de integrar un cambio en `main`.

## Gobernanza

- Esta constitución prevalece sobre cualquier otra práctica o guía del proyecto.
- Las enmiendas se realizan editando este archivo mediante un commit `docs(constitution): …`
  que explique el cambio y su impacto.
- Versionado semántico de la constitución:
  - MAJOR: eliminación o redefinición incompatible de un principio o regla de gobierno.
  - MINOR: nuevo principio o sección, o ampliación material de una guía existente.
  - PATCH: aclaraciones, redacción o correcciones sin cambio semántico.
- Cada plan (`/speckit-plan`) y cada revisión de código MUST verificar el cumplimiento de estos
  principios; cualquier excepción MUST justificarse por escrito en el plan.

## Pendientes

- **JSON Schemas del contrato**: el contrato existe hoy solo como PDF
  (`contract/contrato-v1.1-velocista-sim.pdf`). El principio VII exige un JSON Schema por cada
  tipo de mensaje en `contract/`; deben extraerse del contrato antes de implementar mensajes.

**Version**: 1.1.0 | **Ratified**: 2026-10-16 | **Last Amended**: 2026-10-16
