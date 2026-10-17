// Arranque del panel: crea el estado, abre la sesión en `/ws`, aplica cada mensaje al llegar y
// redibuja como mucho una vez por cuadro con requestAnimationFrame (research R6).
// Todo comando sale por `sendCommand`, que envía, encola el pendiente y registra.

import * as commands from "./commands.js";
import { buildUrl, connect, send } from "./connection.js";
import { addLog, applyMessage, createState, enqueuePending, resetSession } from "./state.js";
import { byTestId } from "./views/dom.js";
import { renderLog } from "./views/log.js";
import { renderTopbar } from "./views/topbar.js";

// Comandos que se anotan en el registro al enviarse: los que cambian la corrida o la sesión.
// Los de ajuste (`set_config`, `set_rate`) llegan a 5 por segundo y su efecto se ve en `config`.
const LOGGED_COMMANDS = new Set(["start", "stop", "reset", "load", "load_track", "set_profile"]);

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

/** Con la conexión cerrada, todo control que envía comandos queda deshabilitado. */
function renderControls() {
  const disabled = state.connection.status !== "open";
  for (const control of root.querySelectorAll("[data-requires-open]")) {
    if (control.disabled !== disabled) control.disabled = disabled;
  }
}

function frame() {
  if (state.dirty) {
    state.dirty = false;
    renderTopbar(root, state);
    renderLog(root, state);
    renderControls();
  }
  requestAnimationFrame(frame);
}

byTestId(root, "btn-reconnect").addEventListener("click", reconnect);
open();
requestAnimationFrame(frame);
