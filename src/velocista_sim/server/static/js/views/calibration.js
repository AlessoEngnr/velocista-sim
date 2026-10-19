// Pestaña Calibración, solo con el simulador (FR-029–FR-033). Por cada parámetro de
// `set_profile`: rótulo en español, unidad, rango como ayuda, campo para el valor medido, estado
// ("MEDIDO <valor> <unidad>" o "POR DEFECTO") y botón Borrar. Aplicar envía un único
// `set_profile` con todos los campos escritos; si alguno no es un número, se marca y no se envía
// nada. Las marcas cambian solo cuando el servidor acepta (`config`), nunca al enviar.

import * as commands from "../commands.js";
import { formatMeasured } from "../format.js";
import { PROFILE_PARAMS, parseDraft } from "../profile-params.js";
import { setCalibrationDraft } from "../state.js";
import { byTestId, setAttr, setHidden, setText } from "./dom.js";

// Borrador ya escrito en cada campo; el campo se reescribe solo si el estado lo cambió (p. ej.
// vacío tras aplicar, o un `hello` nuevo).
const shownDrafts = new Map();

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/** Fila de un parámetro: rótulo y ayuda, campo, estado y botón Borrar. */
function paramRow(param) {
  const row = element("div", "calib-row");

  const label = element("label", "calib-label", param.label);
  label.htmlFor = `calib-${param.key}`;
  label.append(element("span", "calib-help", `${param.unit} · ${param.range}${param.integer ? " · entero" : ""}`));

  const input = element("input", "input value calib-input");
  input.type = "text";
  input.id = `calib-${param.key}`;
  input.dataset.testid = `calib-${param.key}`;
  input.inputMode = param.integer ? "numeric" : "decimal";
  input.autocomplete = "off";
  input.placeholder = "medido";
  input.setAttribute("aria-invalid", "false");
  input.disabled = true;

  const status = element("span", "value calib-state", "POR DEFECTO");
  status.dataset.testid = `calib-${param.key}-state`;

  const clear = element("button", "btn btn-small", "Borrar");
  clear.type = "button";
  clear.dataset.testid = `btn-calib-clear-${param.key}`;
  clear.setAttribute("aria-label", `Borrar el valor medido de ${param.label}`);
  clear.disabled = true;

  row.append(label, input, status, clear);
  return row;
}

/** Arma la pestaña y enlaza sus eventos; `send(command)` envía y devuelve si se envió. */
export function initCalibration(root, state, send) {
  const panel = root.getElementById("panel-calibration");
  const actions = element("div", "calib-actions");
  const apply = element("button", "btn btn-primary btn-small", "Aplicar");
  apply.type = "button";
  apply.dataset.testid = "btn-calib-apply";
  apply.disabled = true;
  const hint = element("p", "hint", "Detén la corrida para cambiar esto");
  hint.dataset.role = "calibration-hint";
  hint.hidden = true;
  actions.append(apply, hint);
  panel.replaceChildren(...PROFILE_PARAMS.map(paramRow), actions);

  for (const param of PROFILE_PARAMS) {
    const input = byTestId(root, `calib-${param.key}`);
    input.addEventListener("input", () => {
      setCalibrationDraft(state, param.key, input.value);
      shownDrafts.set(param.key, input.value);
      setAttr(input, "aria-invalid", "false");
    });
    byTestId(root, `btn-calib-clear-${param.key}`).addEventListener("click", () => {
      send(commands.setProfile({ [param.key]: null }));
    });
  }

  apply.addEventListener("click", () => {
    const measured = {};
    let valid = true;
    for (const param of PROFILE_PARAMS) {
      const text = state.calibration[param.key].draft;
      if (text.trim() === "") continue;
      const value = parseDraft(param, text);
      setAttr(byTestId(root, `calib-${param.key}`), "aria-invalid", String(value === null));
      if (value === null) valid = false;
      else measured[param.key] = value;
    }
    if (valid && Object.keys(measured).length > 0) send(commands.setProfile(measured));
  });
}

function setDisabled(node, disabled) {
  if (node.disabled !== disabled) node.disabled = disabled;
}

/** Dibuja estados y borradores, y habilita la pestaña según la conexión y la corrida. */
export function renderCalibration(root, state) {
  const running = state.run !== null;
  const disabled = running || state.connection.status !== "open" || !state.caps.isSim || state.config === null;
  for (const param of PROFILE_PARAMS) {
    const entry = state.calibration[param.key];
    const input = byTestId(root, `calib-${param.key}`);
    if (shownDrafts.get(param.key) !== entry.draft) {
      shownDrafts.set(param.key, entry.draft);
      input.value = entry.draft;
      setAttr(input, "aria-invalid", "false");
    }
    setDisabled(input, disabled);
    const measured = entry.measured === null ? "POR DEFECTO" : `MEDIDO ${formatMeasured(entry.measured, param.unit)}`;
    const status = byTestId(root, `calib-${param.key}-state`);
    setText(status, measured);
    setAttr(status, "data-state", entry.measured === null ? "default" : "measured");
    setDisabled(byTestId(root, `btn-calib-clear-${param.key}`), disabled || entry.measured === null);
  }
  setDisabled(byTestId(root, "btn-calib-apply"), disabled);
  setHidden(root.querySelector('[data-role="calibration-hint"]'), !running);
}
