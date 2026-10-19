// Pestaña Robot y pista, solo con el simulador (FR-024–FR-028). Elegir un robot envía `load`
// (el servidor reenvía `hello` + `config` y las vistas se rearman con las capacidades nuevas);
// elegir una pista del catálogo abre una sesión nueva con `?track=&robot=` tras confirmar; un
// archivo JSON se envía tal cual con `load_track`. La geometría de la pista nunca llega al panel:
// solo se conocen los ids del catálogo y el `track_id` del `config`.
//
// Los selectores descansan en «Elegir…» y marcan el vigente con «(vigente)»: así también se
// puede volver a elegir el robot o la pista vigentes (un `<select>` nativo no avisa si se elige
// la opción ya seleccionada).

import * as commands from "../commands.js";
import { addLog } from "../state.js";
import { byTestId, setHidden } from "./dom.js";

const CONFIRM_NEW_SESSION =
  "Se abrirá una sesión nueva: se pierden el historial y la calibración de esta sesión. ¿Continuar?";

// Clave de lo dibujado en cada selector; se reconstruye solo si cambió.
const renderedKeys = new Map();

/**
 * Enlaza la pestaña. `send(command)` envía y devuelve si se envió; `reconnect({track, robot})`
 * abre una sesión nueva con esos parámetros de conexión.
 */
export function initRobotTrack(root, state, { send, reconnect }) {
  const robotSelect = byTestId(root, "robot-select");
  const trackSelect = byTestId(root, "track-select");
  const trackFile = byTestId(root, "track-file");

  byTestId(root, "btn-catalog-refresh").addEventListener("click", () => send(commands.list()));

  robotSelect.addEventListener("change", () => {
    const robotId = robotSelect.value;
    robotSelect.value = "";
    if (robotId) send(commands.load(robotId));
  });

  trackSelect.addEventListener("change", () => {
    const trackId = trackSelect.value;
    trackSelect.value = "";
    if (!trackId || !state.hello) return;
    if (window.confirm(CONFIRM_NEW_SESSION)) reconnect({ track: trackId, robot: state.hello.robot.id });
  });

  trackFile.addEventListener("change", async () => {
    const [file] = trackFile.files;
    trackFile.value = ""; // permite volver a elegir el mismo archivo
    if (!file) return;
    let track;
    try {
      track = JSON.parse(await file.text());
    } catch {
      addLog(state, { kind: "local", text: `El archivo no es JSON válido: ${file.name}` });
      return;
    }
    // Si es JSON, el servidor decide si cumple track v1 (`invalid_track`).
    send(commands.loadTrack(track));
  });
}

function option(value, text, { current = false, disabled = false } = {}) {
  const element = document.createElement("option");
  element.value = value;
  element.textContent = text;
  element.disabled = disabled;
  if (current) element.dataset.current = "true";
  return element;
}

/**
 * Llena `select` con `ids` (más el vigente si no está), con «Elegir…» seleccionado. Se rehace
 * solo si cambian las opciones, el vigente o los pendientes, para no cerrar una lista abierta.
 */
function fillSelect(select, ids, current, placeholder, fileTracks) {
  const all = current && !ids.includes(current) ? [...ids, current] : ids;
  const key = JSON.stringify([all, current, [...fileTracks]]);
  if (renderedKeys.get(select) === key) return;
  renderedKeys.set(select, key);
  select.replaceChildren(
    option("", placeholder, { disabled: true }),
    ...all.map((id) => {
      const isCurrent = id === current;
      const fromFile = fileTracks.has(id);
      const marks = [fromFile ? "(archivo)" : "", isCurrent ? "(vigente)" : ""].filter(Boolean).join(" ");
      return option(id, marks ? `${id} ${marks}` : id, { current: isCurrent, disabled: fromFile });
    }),
  );
  select.value = "";
}

function setDisabled(element, disabled) {
  if (element.disabled !== disabled) element.disabled = disabled;
}

/** Dibuja los selectores y habilita la pestaña según la conexión y la corrida. */
export function renderRobotTrack(root, state) {
  const robotSelect = byTestId(root, "robot-select");
  const trackSelect = byTestId(root, "track-select");
  const robotId = state.hello?.robot.id ?? null;
  const trackId = state.config?.track_id ?? null;
  fillSelect(robotSelect, state.catalog?.robots ?? [], robotId, "Elegir robot…", new Set());
  fillSelect(trackSelect, state.catalog?.tracks ?? [], trackId, "Elegir pista…", state.fileTracks);

  const running = state.run !== null;
  const disabled = running || state.connection.status !== "open" || !state.caps.isSim || state.config === null;
  for (const element of [robotSelect, trackSelect, byTestId(root, "track-file"), byTestId(root, "btn-catalog-refresh")]) {
    setDisabled(element, disabled);
  }
  setHidden(root.querySelector('[data-role="robot-track-hint"]'), !running);
}
