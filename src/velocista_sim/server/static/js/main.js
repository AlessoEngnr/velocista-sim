// Arranque del panel: crea el estado, abre la sesión en `/ws`, aplica cada mensaje al llegar y
// redibuja como mucho una vez por cuadro con requestAnimationFrame (research R6).
// Todo comando sale por `sendCommand`, que envía, encola el pendiente y registra.

import * as commands from "./commands.js";
import { buildUrl, connect, send } from "./connection.js";
import {
  addLog, applyMessage, createState, enqueuePending, markAutoStop, resetSession, shouldAutoStop,
} from "./state.js";
import { initControl, renderControl } from "./views/control.js";
import { renderController } from "./views/controller.js";
import { byTestId, setHidden, watchSize } from "./views/dom.js";
import { renderLaps } from "./views/laps.js";
import { renderLog } from "./views/log.js";
import { renderRuns } from "./views/runs.js";
import { renderSensors } from "./views/sensors.js";
import { renderTopbar } from "./views/topbar.js";
import { initTrail, renderTrail } from "./views/trail-view.js";

// Comandos que se anotan en el registro al enviarse: los que cambian la corrida o la sesión.
// Los de ajuste (`set_config`, `set_rate`) llegan a 5 por segundo y su efecto se ve en `config`.
const LOGGED_COMMANDS = new Set(["start", "stop", "reset", "load", "load_track", "set_profile"]);

// Vistas que se redibujan en cada cuadro sucio, en este orden.
const VIEWS = [renderTopbar, renderSensors, renderController, renderTrail, renderLaps, renderRuns, renderControl, renderLog];

const root = document;
const state = createState();

/** Envía un comando del contrato si la conexión está abierta; devuelve si se envió. */
function sendCommand(command) {
  if (state.connection.status !== "open" || !send(command)) return false;
  enqueuePending(state, command);
  if (LOGGED_COMMANDS.has(command.cmd)) addLog(state, { kind: "local", text: `→ ${command.cmd}` });
  state.dirty = true;
  return true;
}

function onMessage(message) {
  const firstConfig = message.type === "config" && state.config === null;
  applyMessage(state, message);
  if (firstConfig) sendCommand(commands.list());
  // Vueltas objetivo: `stop` automático una sola vez por corrida (research R16).
  const lapUpdate = message.type === "telemetry" || (message.type === "event" && message.event === "lap");
  if (lapUpdate && shouldAutoStop(state) && sendCommand(commands.stop())) markAutoStop(state);
  state.dirty = true;
}

function open(url = buildUrl()) {
  state.connection.status = "connecting";
  state.connection.url = url;
  state.connection.closeCode = null;
  state.dirty = true;
  connect(url, {
    onOpen() {
      state.connection.status = "open";
      state.dirty = true;
    },
    onMessage,
    onInvalid() {
      addLog(state, { kind: "warning", text: "Frame ignorado: no es JSON de texto" });
    },
    onClose(code) {
      state.connection.status = "closed";
      state.connection.closeCode = code;
      state.pending = [];
      addLog(state, { kind: "local", text: `Conexión cerrada (código ${code})` });
    },
  });
}

function reconnect() {
  resetSession(state);
  open();
}

/**
 * Muestra u oculta lo que depende del `hello` (FR-006, FR-035): `data-requires="sim"` solo con
 * el simulador y `data-requires="laps"` solo si el robot mide vueltas. Sin `sim_truth`, la
 * columna central muestra un aviso en lugar del rastro.
 */
function renderCapabilities() {
  const { isSim, hasLaps } = state.caps;
  for (const element of root.querySelectorAll("[data-requires]")) {
    const required = element.dataset.requires;
    setHidden(element, (required === "sim" && !isSim) || (required === "laps" && !hasLaps));
  }
  setHidden(root.querySelector('[data-role="no-sim-truth"]'), state.hello === null || isSim);
}

/** Con la conexión cerrada, todo control marcado `data-requires-open` queda deshabilitado. */
function renderOpenControls() {
  const disabled = state.connection.status !== "open";
  for (const control of root.querySelectorAll("[data-requires-open]")) {
    if (control.disabled !== disabled) control.disabled = disabled;
  }
}

function frame() {
  if (state.dirty) {
    state.dirty = false;
    renderCapabilities();
    renderOpenControls();
    for (const view of VIEWS) view(root, state);
  }
  requestAnimationFrame(frame);
}

function markDirty() {
  state.dirty = true;
}

initControl(root, state, sendCommand);
byTestId(root, "btn-reconnect").addEventListener("click", reconnect);
initTrail(root, state);
watchSize(byTestId(root, "sensors-canvas"), markDirty);
watchSize(byTestId(root, "trail-canvas"), markDirty);
open();
requestAnimationFrame(frame);
