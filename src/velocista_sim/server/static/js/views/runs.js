// Tarjeta Corridas: resumen de cada corrida terminada en la sesión, la más reciente primero
// (FR-022). Los valores `null` del contrato se muestran como "—".

import { MISSING, formatGain, formatSeconds } from "../format.js";
import { byTestId } from "./dom.js";

let renderedHead = null;
let renderedLength = -1;

function row(label, value) {
  const div = document.createElement("div");
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  dd.className = "value";
  dd.textContent = value;
  div.append(dt, dd);
  return div;
}

function summaryItem(summary) {
  const item = document.createElement("li");
  item.dataset.runId = summary.run_id;
  const title = document.createElement("p");
  title.className = "summary-title";
  title.textContent = `${summary.run_id} · ${formatSeconds(summary.t_ms)}`;
  const config = summary.config;
  const values = document.createElement("dl");
  values.className = "summary-values";
  values.append(
    row("VUELTAS", summary.laps === null ? MISSING : String(summary.laps)),
    row("MEJOR", formatSeconds(summary.best_lap_ms)),
    row("PROMEDIO", formatSeconds(summary.avg_lap_ms)),
    row("SALIDAS", String(summary.off_tracks)),
    row("PISTA", summary.track_id ?? MISSING),
    row("CONTROL", config.controller),
    row("KP", formatGain(config.params.kp)),
    row("KI", formatGain(config.params.ki)),
    row("KD", formatGain(config.params.kd)),
    row("BASE", String(config.base_speed)),
    row("CAMBIÓ CONFIG", summary.config_changed ? "sí" : "no"),
  );
  item.append(title, values);
  return item;
}

/** Dibuja la lista de resúmenes si cambió. */
export function renderRuns(root, state) {
  const head = state.summaries[0] ?? null;
  if (head === renderedHead && state.summaries.length === renderedLength) return;
  renderedHead = head;
  renderedLength = state.summaries.length;
  byTestId(root, "summaries").replaceChildren(...state.summaries.map(summaryItem));
}
