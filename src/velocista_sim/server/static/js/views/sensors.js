// Tarjeta Regleta: una barra por sensor, marcador de `line_position`, error y aviso de línea
// perdida (FR-014, FR-015, research R7). El aviso es texto, no solo color (FR-042).

import { formatError, formatLinePosition } from "../format.js";
import { byTestId, cssVar, fitCanvas, setText } from "./dom.js";

const GAP = 2;

/** Dibuja la regleta con la última telemetría. */
export function renderSensors(root, state) {
  const telemetry = state.telemetry.last;
  const lost = telemetry?.line_lost === true;
  setText(byTestId(root, "line-position"), formatLinePosition(telemetry?.line_position));
  setText(byTestId(root, "error"), formatError(telemetry?.error));
  setText(byTestId(root, "line-lost"), lost ? "▲ LÍNEA PERDIDA" : "");
  drawSensors(byTestId(root, "sensors-canvas"), state, telemetry, lost);
}

function drawSensors(canvas, state, telemetry, lost) {
  const { context, width, height } = fitCanvas(canvas);
  const count = state.caps.sensorCount;
  if (!telemetry || count === 0 || state.caps.adcMax === 0) return;

  const barWidth = (width - GAP * (count + 1)) / count;
  context.fillStyle = cssVar("--muted");
  telemetry.sensors.forEach((reading, i) => {
    const barHeight = Math.max(1, (Math.min(reading, state.caps.adcMax) / state.caps.adcMax) * (height - 8));
    context.fillRect(GAP + i * (barWidth + GAP), height - 4 - barHeight, barWidth, barHeight);
  });

  // `line_position` va de 0 (centro del primer sensor) a (n − 1) × 1000 (centro del último).
  const fraction = telemetry.line_position / ((count - 1) * 1000);
  const x = GAP + barWidth / 2 + fraction * (width - 2 * GAP - barWidth);
  context.strokeStyle = lost ? cssVar("--warn") : cssVar("--accent");
  context.lineWidth = 2;
  context.setLineDash(lost ? [4, 4] : []);
  context.beginPath();
  context.moveTo(x, 0);
  context.lineTo(x, height);
  context.stroke();
  context.setLineDash([]);
}
