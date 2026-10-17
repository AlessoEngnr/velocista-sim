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
