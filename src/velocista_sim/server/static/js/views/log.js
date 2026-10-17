// Registro de eventos y errores (tarjeta Registro, FR-021, FR-042).
// Una fila por entrada, la más reciente primero, con el tiempo de la sesión en segundos. Los
// errores muestran `code · cmd · message` en rojo y con el símbolo ✕ (no solo color).

import { formatSeconds } from "../format.js";
import { byTestId } from "./dom.js";

// Conjunto cerrado de códigos de error del contrato v1; cualquier otro se muestra como genérico.
const KNOWN_ERROR_CODES = new Set([
  "invalid_json", "unknown_cmd", "invalid_params", "out_of_range", "sim_only", "run_active",
  "no_run", "unknown_robot", "unknown_track", "invalid_track", "unsupported_version",
]);

const SYMBOLS = { error: "✕ ", warning: "▲ ", local: "", event: "" };

let renderedHead = null;
let renderedLength = -1;

function entryText(entry) {
  if (entry.kind !== "error") return entry.text;
  const code = KNOWN_ERROR_CODES.has(entry.code) ? entry.code : "error";
  return [code, entry.cmd, entry.text].filter(Boolean).join(" · ");
}

/** Dibuja el registro si cambió desde el último cuadro. */
export function renderLog(root, state) {
  const head = state.log[0] ?? null;
  if (head === renderedHead && state.log.length === renderedLength) return;
  renderedHead = head;
  renderedLength = state.log.length;

  const list = byTestId(root, "log");
  const items = state.log.map((entry) => {
    const item = document.createElement("li");
    item.dataset.kind = entry.kind;
    const time = document.createElement("span");
    time.className = "log-time";
    time.textContent = formatSeconds(entry.tMs);
    const text = document.createElement("span");
    text.className = "log-text";
    text.textContent = SYMBOLS[entry.kind] + entryText(entry);
    item.append(time, text);
    return item;
  });
  list.replaceChildren(...items);
}
