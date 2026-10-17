// Tarjeta Vueltas: última, mejor y promedio, e historial de la corrida (FR-020). Mientras corre
// se calculan de los `event lap`; al terminar se muestran los del `summary`. Se oculta si el
// robot no mide vueltas (`lap_timing = false`).

import { MISSING, formatSeconds } from "../format.js";
import { byTestId, setText } from "./dom.js";

const NO_LAPS = [];

let renderedLaps = null;
let renderedCount = -1;
let renderedBest = null;

/** Dibuja la tarjeta Vueltas. */
export function renderLaps(root, state) {
  const run = state.run ?? state.lastRun;
  const summary = state.run ? null : state.summaries[0];
  const best = summary ? summary.best_lap_ms : (run?.bestLapMs ?? null);
  const avg = summary ? summary.avg_lap_ms : (run?.avgLapMs ?? null);
  const telemetry = state.telemetry.last;
  const lap = state.run && telemetry?.running ? telemetry.lap : null;
  setText(root.querySelector('[data-role="lap-running"]'), lap ? `${lap.n + 1} · ${formatSeconds(lap.current_ms)}` : MISSING);
  setText(byTestId(root, "lap-last"), formatSeconds(run?.lastLapMs));
  setText(byTestId(root, "lap-best"), formatSeconds(best));
  setText(byTestId(root, "lap-avg"), formatSeconds(avg));

  const laps = run?.laps ?? NO_LAPS;
  if (laps === renderedLaps && laps.length === renderedCount && best === renderedBest) return;
  renderedLaps = laps;
  renderedCount = laps.length;
  renderedBest = best;

  const items = laps.map((lap) => {
    const item = document.createElement("li");
    const name = document.createElement("span");
    name.textContent = `VUELTA ${lap.n}`;
    const time = document.createElement("span");
    time.className = lap.lapMs === best ? "value value-best" : "value";
    time.textContent = formatSeconds(lap.lapMs) + (lap.lapMs === best ? " ★" : "");
    item.append(name, time);
    return item;
  });
  byTestId(root, "lap-history").replaceChildren(...items);
}
