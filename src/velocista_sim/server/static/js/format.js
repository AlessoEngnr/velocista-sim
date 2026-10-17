// Formato fijo de cada magnitud con su unidad (research R10, FR-040).
// Todo número visible del panel pasa por aquí: decimales fijos, signo explícito ("+" o el signo
// menos tipográfico U+2212) cuando la magnitud puede ser negativa, y "—" si falta el valor.
// Las unidades son las del contrato; los tiempos se muestran en segundos y nunca en km/h.

export const MISSING = "—";
const MINUS = "−";

function isNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function fixed(value, decimals, signed) {
  const text = Math.abs(value).toFixed(decimals);
  // El signo sale del valor ya redondeado: −0.04 con un decimal es "0.0", no "−0.0".
  if (Number(text) === 0) return text;
  if (value < 0) return MINUS + text;
  return signed ? "+" + text : text;
}

function withUnit(value, decimals, signed, unit) {
  if (!isNumber(value)) return MISSING;
  const text = fixed(value, decimals, signed);
  return unit ? `${text} ${unit}` : text;
}

/** `error` de la línea: entero con signo, en milésimas de sensor. */
export function formatError(value) {
  return withUnit(value, 0, true, "‰ sensor");
}

/** `line_position`: entero, en milésimas de sensor. */
export function formatLinePosition(value) {
  return withUnit(value, 0, false, "‰ sensor");
}

/** Lectura cruda de un sensor. */
export function formatAdc(value) {
  return withUnit(value, 0, false, "ADC");
}

/** Términos del PID (`control.p/i/d/out`): adimensionales, 1 decimal con signo. */
export function formatPid(value) {
  return withUnit(value, 1, true, "");
}

/** Comando de motor: entero con signo, −255…255. */
export function formatPwm(value) {
  return withUnit(value, 0, true, "PWM");
}

/** `battery_v`. */
export function formatVolts(value) {
  return withUnit(value, 2, false, "V");
}

/** `sim_truth.speed_mps`. */
export function formatSpeed(value) {
  return withUnit(value, 2, false, "m/s");
}

/** `sim_truth.distance_m`. */
export function formatDistance(value) {
  return withUnit(value, 2, false, "m");
}

/** `sim_truth.x` / `sim_truth.y`. */
export function formatCoord(value) {
  return withUnit(value, 3, true, "m");
}

/** `sim_truth.theta`. */
export function formatTheta(value) {
  return withUnit(value, 3, true, "rad");
}

/** Tiempos del contrato (llegan en ms) mostrados en segundos con 3 decimales. */
export function formatSeconds(ms) {
  return isNumber(ms) ? withUnit(ms / 1000, 3, false, "s") : MISSING;
}

/** `rate_hz`. */
export function formatHz(value) {
  return withUnit(value, 0, false, "Hz");
}

/** Ganancias del PID (`kp`, `ki`, `kd`) en los campos de ajuste: 4 decimales, sin unidad. */
export function formatGain(value) {
  return withUnit(value, 4, false, "");
}
