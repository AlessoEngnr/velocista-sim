// Los 12 parámetros físicos y de calibración que acepta `set_profile` (contrato v1, FR-029), en
// el orden y con los valores de data-model.md. `adc_noise` es el ruido de la regleta (± ADC).
// `range` es el texto de ayuda y `bounds` el mismo rango para validar: el panel no envía un
// valor fuera del rango del contrato, así todo `set_profile` enviado cumple el esquema (FR-037).
// `bounds`: `min` (incluido), `above` (excluido, "> above") y `max` (incluido).
//
// El contrato no envía al cliente el `default` ni el `source` del perfil, así que el panel solo
// muestra si cada parámetro tiene un valor medido aceptado en esta sesión (FR-032).

export const PROFILE_PARAMS = Object.freeze([
  { key: "sensor_pitch_m", label: "Separación entre sensores", unit: "m", range: "> 0", integer: false, bounds: { above: 0 } },
  { key: "sensor_offset_m", label: "Distancia de la regleta al eje", unit: "m", range: "> 0", integer: false, bounds: { above: 0 } },
  { key: "adc_white", label: "Lectura sobre blanco", unit: "ADC", range: "0–65535", integer: true, bounds: { min: 0, max: 65535 } },
  { key: "adc_black", label: "Lectura sobre negro", unit: "ADC", range: "0–65535", integer: true, bounds: { min: 0, max: 65535 } },
  { key: "adc_noise", label: "Ruido de la regleta", unit: "ADC (±)", range: "≥ 0", integer: true, bounds: { min: 0 } },
  { key: "max_speed_mps", label: "Velocidad máxima (PWM 255)", unit: "m/s", range: "> 0", integer: false, bounds: { above: 0 } },
  { key: "motor_tau_ms", label: "Constante de tiempo del motor", unit: "ms", range: "> 0", integer: false, bounds: { above: 0 } },
  { key: "wheelbase_m", label: "Distancia entre ruedas", unit: "m", range: "> 0", integer: false, bounds: { above: 0 } },
  { key: "max_lateral_accel_mps2", label: "Agarre lateral máximo", unit: "m/s²", range: "> 0", integer: false, bounds: { above: 0 } },
  { key: "turbine_suction_n", label: "Succión de la turbina", unit: "N", range: "≥ 0", integer: false, bounds: { min: 0 } },
  { key: "encoder_ticks_per_rev", label: "Pulsos del encoder por vuelta", unit: "ticks", range: "≥ 1", integer: true, bounds: { min: 1 } },
  { key: "control_period_ms", label: "Período de control", unit: "ms", range: "> 0", integer: false, bounds: { above: 0 } },
].map((param) => Object.freeze({ ...param, bounds: Object.freeze(param.bounds) })));

/**
 * Interpreta lo escrito en el campo de `param`: devuelve el número, o `null` si no es un número
 * finito, no es entero cuando `param.integer`, o queda fuera del rango del contrato. Acepta coma
 * decimal.
 */
export function parseDraft(param, text) {
  const trimmed = text.trim().replace(",", ".");
  if (!/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(trimmed)) return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value)) return null;
  if (param.integer && !Number.isInteger(value)) return null;
  const { min, above, max } = param.bounds;
  if (min !== undefined && value < min) return null;
  if (above !== undefined && value <= above) return null;
  if (max !== undefined && value > max) return null;
  return value;
}
