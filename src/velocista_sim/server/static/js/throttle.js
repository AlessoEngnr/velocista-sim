// Envío limitado para los sliders de ajuste (research R8, FR-010).
// `throttle(fn, intervalMs)` devuelve una función que llama `fn` como mucho una vez cada
// `intervalMs`: la primera llamada sale enseguida y, si llegan más dentro del intervalo, se
// guarda solo el último valor y se envía al cumplirse el intervalo (envío final garantizado).
// `flush()` envía ya el valor pendiente, si lo hay; se usa al soltar el slider.

/** Limita `fn` a una llamada cada `intervalMs`, con envío inicial y final. */
export function throttle(fn, intervalMs = 200) {
  let lastSent = -Infinity;
  let timer = null;
  let pending = null; // { args } del último valor sin enviar, o null

  function fire() {
    clearTimeout(timer);
    timer = null;
    const { args } = pending;
    pending = null;
    lastSent = performance.now();
    fn(...args);
  }

  function throttled(...args) {
    pending = { args };
    const wait = lastSent + intervalMs - performance.now();
    if (wait <= 0) fire();
    else if (timer === null) timer = setTimeout(fire, wait);
  }

  /** Envía ya el último valor pendiente (no hace nada si no hay). */
  throttled.flush = () => {
    if (pending !== null) fire();
  };

  /** Descarta el valor pendiente sin enviarlo. */
  throttled.cancel = () => {
    clearTimeout(timer);
    timer = null;
    pending = null;
  };

  return throttled;
}
