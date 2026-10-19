// Ayudas mínimas de DOM compartidas por las vistas. Escriben solo si el valor cambió, para no
// tocar el DOM de más cuando la telemetría llega a 100 Hz (research R6).

/** Elemento con `data-testid` (contracts/ui-hooks.md) dentro de `root`. */
export function byTestId(root, id) {
  return root.querySelector(`[data-testid="${id}"]`);
}

/** Cambia el texto del elemento solo si es distinto. */
export function setText(element, text) {
  if (element && element.textContent !== text) element.textContent = text;
}

/** Cambia un atributo solo si es distinto. */
export function setAttr(element, name, value) {
  if (element && element.getAttribute(name) !== value) element.setAttribute(name, value);
}

/** Oculta o muestra el elemento. */
export function setHidden(element, hidden) {
  if (element && element.hidden !== hidden) element.hidden = hidden;
}

/** Valor de un token de color de `panel.css` (p. ej. `--accent`). */
export function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/**
 * Ajusta el tamaño interno del canvas a su tamaño en pantalla por `devicePixelRatio` y devuelve
 * el contexto ya escalado, con el ancho y alto en píxeles CSS.
 */
export function fitCanvas(canvas) {
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  const pixelWidth = Math.max(1, Math.round(width * ratio));
  const pixelHeight = Math.max(1, Math.round(height * ratio));
  if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
  if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
  const context = canvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, width, height);
  return { context, width, height };
}

/** Llama `onResize` cada vez que el canvas cambia de tamaño en pantalla. */
export function watchSize(canvas, onResize) {
  new ResizeObserver(onResize).observe(canvas);
}
