// Tarjeta Control: Iniciar, Detener, Reiniciar, vueltas objetivo, pestañas (FR-007, FR-045) y
// la pestaña Ajuste (FR-009–FR-013). Los botones se habilitan según la conexión y la corrida; los
// solo-sim se ocultan con un robot real. Los comandos salen por `send` (el `sendCommand` de
// main.js). Los controles de ajuste muestran `state.drafts`: el valor confirmado por el último
// `config`, o el que el usuario está moviendo o acaba de enviar.

import * as commands from "../commands.js";
import { formatGain } from "../format.js";
import { parseNumber } from "../numbers.js";
import { markAutoStop, setDraft, setLapTarget, shouldAutoStop } from "../state.js";
import { throttle } from "../throttle.js";
import { clearTrail } from "../trail.js";
import { byTestId, setAttr, setHidden } from "./dom.js";

const TABS = ["tuning", "robot-track", "calibration"];

// Controles de la pestaña Ajuste con los recorridos de research R9. `range` es el slider (`null`:
// solo campo numérico); `integer` y `bounds` validan el campo numérico, con el rango del contrato
// o uno más estricto (FR-011, FR-012; tests/browser/test_panel_ranges.py). Las ganancias aceptan
// cualquier valor ≥ 0, también fuera del recorrido del slider.
export const TUNING = Object.freeze([
  { field: "kp", testId: "kp", label: "KP", range: { min: 0, max: 0.2, step: 0.0005 }, format: formatGain, integer: false, bounds: { min: 0 } },
  { field: "ki", testId: "ki", label: "KI", range: { min: 0, max: 0.01, step: 0.0001 }, format: formatGain, integer: false, bounds: { min: 0 } },
  { field: "kd", testId: "kd", label: "KD", range: { min: 0, max: 5, step: 0.01 }, format: formatGain, integer: false, bounds: { min: 0 } },
  {
    field: "base_speed", testId: "base-speed", label: "VEL. BASE", unit: "PWM",
    range: { min: 0, max: 255, step: 1 }, format: String, integer: true, bounds: { min: 0, max: 255 },
  },
  {
    field: "rate_hz", testId: "rate", label: "FRECUENCIA", unit: "Hz",
    range: null, format: String, integer: true, bounds: { min: 10, max: 100 },
  },
].map((control) => Object.freeze(control)));

// Valor de cada draft ya escrito en sus controles; se reescriben solo si cambió.
const shown = new Map();

/** Valor válido escrito en el campo de `control`, o `null`. */
export function parseTuning(control, text) {
  return parseNumber(text, control);
}

/** Comando que fija `value` en `field`: `set_rate` para la frecuencia, `set_config` si no. */
function tuningCommand(field, value) {
  return field === "rate_hz" ? commands.setRate(value) : commands.setConfig({ [field]: value });
}

function createInput(type, testId, field) {
  const input = document.createElement("input");
  input.type = type;
  input.id = testId;
  input.dataset.testid = testId;
  input.dataset.field = field;
  input.disabled = true;
  return input;
}

/** Fila de la pestaña Ajuste: rótulo, slider (si tiene), campo numérico y unidad. */
function tuningRow(control) {
  const row = document.createElement("div");
  row.className = "tuning-row";
  const label = document.createElement("label");
  label.htmlFor = `${control.testId}-input`;
  label.textContent = control.label;
  row.append(label);

  if (control.range) {
    const range = createInput("range", `${control.testId}-range`, control.field);
    range.className = "range";
    range.min = String(control.range.min);
    range.max = String(control.range.max);
    range.step = String(control.range.step);
    range.setAttribute("aria-label", `${control.label} (deslizante)`);
    row.append(range);
  } else {
    row.append(document.createElement("span"));
  }

  const input = createInput("text", `${control.testId}-input`, control.field);
  input.className = "input value";
  input.inputMode = control.integer ? "numeric" : "decimal";
  input.autocomplete = "off";
  input.setAttribute("aria-invalid", "false");

  const unit = document.createElement("span");
  unit.className = "unit";
  unit.textContent = control.unit ?? "";
  row.append(input, unit);
  return row;
}

/**
 * Arma la pestaña Ajuste y enlaza sus eventos. El slider envía durante el arrastre limitado por
 * `throttle` (200 ms por campo) y fuerza el valor final al soltar; el campo numérico envía al
 * confirmar (`change`), sin límite, y si el texto no es válido lo marca y no envía nada.
 */
function initTuning(root, state, send) {
  root.getElementById("panel-tuning").replaceChildren(...TUNING.map(tuningRow));

  for (const control of TUNING) {
    const { field } = control;
    const input = byTestId(root, `${control.testId}-input`);
    input.addEventListener("change", () => {
      const value = parseTuning(control, input.value);
      setAttr(input, "aria-invalid", String(value === null));
      if (value === null) return;
      setDraft(state, field, value);
      shown.delete(field); // reescribe el campo con el formato fijo aunque el valor no cambie
      send(tuningCommand(field, value));
    });

    if (!control.range) continue;
    const range = byTestId(root, `${control.testId}-range`);
    const sendLimited = throttle((value) => send(tuningCommand(field, value)), 200);
    range.addEventListener("input", () => {
      const value = Number(range.value);
      setDraft(state, field, value);
      sendLimited(value);
    });
    range.addEventListener("change", sendLimited.flush);
    range.addEventListener("pointerup", sendLimited.flush);
  }
}

/** Escribe en los controles de ajuste los drafts que cambiaron y los habilita según la sesión. */
function renderTuning(root, state) {
  const disabled = state.connection.status !== "open" || state.config === null;
  for (const control of TUNING) {
    const { field } = control;
    const draft = state.drafts[field];
    const input = byTestId(root, `${control.testId}-input`);
    const range = control.range ? byTestId(root, `${control.testId}-range`) : null;
    setDisabled(input, disabled);
    if (range) setDisabled(range, disabled);
    if (shown.has(field) && shown.get(field) === draft.value) continue;
    shown.set(field, draft.value);
    input.value = draft.value === null ? "" : control.format(draft.value);
    setAttr(input, "aria-invalid", "false");
    // Mientras se arrastra, el slider ya muestra lo que eligió el usuario. Con un valor fuera del
    // recorrido, el navegador lo deja en el extremo (R9).
    if (range && !draft.dragging) range.value = draft.value === null ? String(control.range.min) : String(draft.value);
  }
}

/** Enlaza los controles de la tarjeta; `send(command)` envía y devuelve si se envió. */
export function initControl(root, state, send) {
  initTuning(root, state, send);

  byTestId(root, "btn-start").addEventListener("click", () => {
    if (send(commands.start())) clearTrail(state.trail);
  });
  byTestId(root, "btn-stop").addEventListener("click", () => send(commands.stop()));
  byTestId(root, "btn-reset").addEventListener("click", () => {
    if (send(commands.reset())) clearTrail(state.trail);
  });

  const lapTarget = byTestId(root, "lap-target-input");
  lapTarget.addEventListener("change", () => {
    const valid = setLapTarget(state, lapTarget.value);
    setAttr(lapTarget, "aria-invalid", String(!valid));
    if (valid && shouldAutoStop(state) && send(commands.stop())) markAutoStop(state);
    state.dirty = true;
  });

  for (const name of TABS) {
    byTestId(root, `tab-${name}`).addEventListener("click", () => selectTab(root, name));
  }
}

function selectTab(root, selected) {
  for (const name of TABS) {
    setAttr(byTestId(root, `tab-${name}`), "aria-selected", String(name === selected));
    setHidden(root.getElementById(`panel-${name}`), name !== selected);
  }
}

function setDisabled(element, disabled) {
  if (element.disabled !== disabled) element.disabled = disabled;
}

/** Habilita y oculta los controles según la conexión, la corrida y el `hello`. */
export function renderControl(root, state) {
  const open = state.connection.status === "open";
  const running = state.run !== null;
  setDisabled(byTestId(root, "btn-start"), !open || running);
  setDisabled(byTestId(root, "btn-stop"), !open || !running);
  setDisabled(byTestId(root, "btn-reset"), !open || running || !state.caps.isSim);

  // Si una pestaña solo-sim estaba elegida y llega un robot real, se vuelve a Ajuste.
  const selected = TABS.find((name) => byTestId(root, `tab-${name}`).getAttribute("aria-selected") === "true");
  if (!state.caps.isSim && selected !== "tuning") selectTab(root, "tuning");

  renderTuning(root, state);
}
