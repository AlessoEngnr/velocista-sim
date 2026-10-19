// Rastro de `sim_truth`: buffer circular de posiciones (data-model.md, Trail; research R7).
// Guarda hasta `capacity` puntos en dos Float32Array; al llenarse sobrescribe el más antiguo.
// `bounds` es la caja que contiene todos los puntos guardados, para escalar el dibujo.

/** Rastro vacío con lugar para `capacity` puntos. */
export function createTrail(capacity = 5000) {
  return {
    capacity,
    xs: new Float32Array(capacity),
    ys: new Float32Array(capacity),
    start: 0,
    length: 0,
    bounds: emptyBounds(),
    pose: null,
  };
}

function emptyBounds() {
  return { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
}

function extend(bounds, x, y) {
  if (x < bounds.minX) bounds.minX = x;
  if (x > bounds.maxX) bounds.maxX = x;
  if (y < bounds.minY) bounds.minY = y;
  if (y > bounds.maxY) bounds.maxY = y;
}

function recomputeBounds(trail) {
  trail.bounds = emptyBounds();
  forEachPoint(trail, (x, y) => extend(trail.bounds, x, y));
}

/** Agrega un punto (m) y fija la pose actual; con el buffer lleno pisa el más antiguo. */
export function pushPoint(trail, x, y, theta) {
  trail.pose = { x, y, theta };
  if (trail.length < trail.capacity) {
    const index = (trail.start + trail.length) % trail.capacity;
    trail.xs[index] = x;
    trail.ys[index] = y;
    trail.length += 1;
    extend(trail.bounds, x, y);
    return;
  }
  const oldX = trail.xs[trail.start];
  const oldY = trail.ys[trail.start];
  trail.xs[trail.start] = x;
  trail.ys[trail.start] = y;
  trail.start = (trail.start + 1) % trail.capacity;
  const { minX, maxX, minY, maxY } = trail.bounds;
  // Solo hace falta recalcular la caja si el punto descartado estaba en su borde.
  if (oldX <= minX || oldX >= maxX || oldY <= minY || oldY >= maxY) recomputeBounds(trail);
  else extend(trail.bounds, x, y);
}

/** Vacía el rastro (la pose actual se conserva). */
export function clearTrail(trail) {
  trail.start = 0;
  trail.length = 0;
  trail.bounds = emptyBounds();
}

/** Recorre los puntos del más antiguo al más reciente: `fn(x, y, i)`. */
export function forEachPoint(trail, fn) {
  for (let i = 0; i < trail.length; i += 1) {
    const index = (trail.start + i) % trail.capacity;
    fn(trail.xs[index], trail.ys[index], i);
  }
}
