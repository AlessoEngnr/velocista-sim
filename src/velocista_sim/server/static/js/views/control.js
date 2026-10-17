// Tarjeta Control: Iniciar, Detener, Reiniciar, vueltas objetivo y pestañas (FR-007, FR-045).
// Los botones se habilitan según la conexión y la corrida; los solo-sim se ocultan con un robot
// real. Los comandos salen por `send` (el `sendCommand` de main.js).

import * as commands from "../commands.js";
import { markAutoStop, setLapTarget, shouldAutoStop } from "../state.js";
import { clearTrail } from "../trail.js";
import { byTestId, setAttr, setHidden } from "./dom.js";

const TABS = ["tuning", "robot-track", "calibration"];

/** Enlaza los controles de la tarjeta; `send(command)` envía y devuelve si se envió. */
export function initControl(root, state, send) {
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
}
