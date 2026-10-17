// Tarjeta Rastro: recorrido de `sim_truth` y franja de velocidad, distancia y pose (FR-018,
// research R7). Solo existe en el simulador: con un robot real la tarjeta se oculta y la
// columna central muestra un aviso.

import { formatCoord, formatDistance, formatSpeed, formatTheta } from "../format.js";
import { clearTrail, forEachPoint } from "../trail.js";
import { byTestId, cssVar, fitCanvas, setAttr, setText } from "./dom.js";

const MARGIN = 16;
const POSE_SIZE = 9;

/** Enlaza Limpiar rastro: acción local, no envía ningún comando. */
export function initTrail(root, state) {
  byTestId(root, "btn-trail-clear").addEventListener("click", () => {
    clearTrail(state.trail);
    state.dirty = true;
  });
}

/** Dibuja el rastro, la pose actual y la franja de valores. */
export function renderTrail(root, state) {
  const truth = state.telemetry.last?.sim_truth;
  setText(byTestId(root, "speed"), formatSpeed(truth?.speed_mps));
  setText(byTestId(root, "distance"), formatDistance(truth?.distance_m));
  setText(byTestId(root, "pose-x"), formatCoord(truth?.x));
  setText(byTestId(root, "pose-y"), formatCoord(truth?.y));
  setText(byTestId(root, "theta"), formatTheta(truth?.theta));

  const canvas = byTestId(root, "trail-canvas");
  setAttr(canvas, "data-points", String(state.trail.length));
  if (!canvas.hidden && canvas.clientWidth > 0) drawTrail(canvas, state.trail);
}

function drawTrail(canvas, trail) {
  const { context, width, height } = fitCanvas(canvas);
  const pose = trail.pose;
  const bounds = { ...trail.bounds };
  if (pose) {
    bounds.minX = Math.min(bounds.minX, pose.x);
    bounds.maxX = Math.max(bounds.maxX, pose.x);
    bounds.minY = Math.min(bounds.minY, pose.y);
    bounds.maxY = Math.max(bounds.maxY, pose.y);
  }
  if (!Number.isFinite(bounds.minX)) return;

  // Misma escala en x e y, eje y hacia arriba, caja centrada; como mínimo 0,5 m de lado.
  const spanX = Math.max(bounds.maxX - bounds.minX, 0.5);
  const spanY = Math.max(bounds.maxY - bounds.minY, 0.5);
  const scale = Math.min((width - 2 * MARGIN) / spanX, (height - 2 * MARGIN) / spanY);
  const centerX = (bounds.minX + bounds.maxX) / 2;
  const centerY = (bounds.minY + bounds.maxY) / 2;
  const toX = (x) => width / 2 + (x - centerX) * scale;
  const toY = (y) => height / 2 - (y - centerY) * scale;

  if (trail.length > 1) {
    context.strokeStyle = cssVar("--accent");
    context.lineWidth = 1.5;
    context.lineJoin = "round";
    context.beginPath();
    forEachPoint(trail, (x, y, i) => {
      if (i === 0) context.moveTo(toX(x), toY(y));
      else context.lineTo(toX(x), toY(y));
    });
    context.stroke();
  }

  if (pose) {
    // Triángulo blanco que apunta según `theta` (radianes, antihorario desde +x).
    context.save();
    context.translate(toX(pose.x), toY(pose.y));
    context.rotate(-pose.theta);
    context.fillStyle = cssVar("--text");
    context.beginPath();
    context.moveTo(POSE_SIZE, 0);
    context.lineTo(-POSE_SIZE * 0.7, POSE_SIZE * 0.6);
    context.lineTo(-POSE_SIZE * 0.7, -POSE_SIZE * 0.6);
    context.closePath();
    context.fill();
    context.restore();
  }
}
