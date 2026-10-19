// Los 12 parámetros físicos y de calibración que acepta `set_profile` (contrato v1, FR-029), en
// el orden y con los valores de data-model.md. `adc_noise` es el ruido de la regleta (± ADC).
// `bounds` es el rango del contrato; el panel no envía un valor fuera de él, así todo
// `set_profile` enviado cumple el esquema (FR-037). Los parámetros con `adcScaled` se limitan
// además a la escala del ADC del robot: 0 a 2^`adc_bits` − 1 según el `hello` (4095 con 12 bits),
// más estricto que el 0–65535 genérico del contrato.
//
// El contrato no envía al cliente el `default` ni el `source` del perfil, así que el panel solo
// muestra si cada parámetro tiene un valor medido aceptado en esta sesión (FR-032).

import { parseNumber, rangeText } from "./numbers.js";

const ADC = { min: 0, max: 65535 };
const POSITIVE = { above: 0 };

export const PROFILE_PARAMS = Object.freeze([
  { key: "sensor_pitch_m", label: "Separación entre sensores", unit: "m", integer: false, bounds: POSITIVE },
  { key: "sensor_offset_m", label: "Distancia de la regleta al eje", unit: "m", integer: false, bounds: POSITIVE },
  { key: "adc_white", label: "Lectura sobre blanco", unit: "ADC", integer: true, bounds: ADC, adcScaled: true },
  { key: "adc_black", label: "Lectura sobre negro", unit: "ADC", integer: true, bounds: ADC, adcScaled: true },
  { key: "adc_noise", label: "Ruido de la regleta", unit: "ADC (±)", integer: true, bounds: { min: 0 }, adcScaled: true },
  { key: "max_speed_mps", label: "Velocidad máxima (PWM 255)", unit: "m/s", integer: false, bounds: POSITIVE },
  { key: "motor_tau_ms", label: "Constante de tiempo del motor", unit: "ms", integer: false, bounds: POSITIVE },
  { key: "wheelbase_m", label: "Distancia entre ruedas", unit: "m", integer: false, bounds: POSITIVE },
  { key: "max_lateral_accel_mps2", label: "Agarre lateral máximo", unit: "m/s²", integer: false, bounds: POSITIVE },
  { key: "turbine_suction_n", label: "Succión de la turbina", unit: "N", integer: false, bounds: { min: 0 } },
  { key: "encoder_ticks_per_rev", label: "Pulsos del encoder por vuelta", unit: "ticks", integer: true, bounds: { min: 1 } },
  { key: "control_period_ms", label: "Período de control", unit: "ms", integer: false, bounds: POSITIVE },
].map((param) => Object.freeze({ ...param, bounds: Object.freeze({ ...param.bounds }) })));

/** Rango vigente de `param`: el del contrato, recortado a la escala del ADC si corresponde. */
export function paramBounds(param, adcBits = null) {
  if (!param.adcScaled || !Number.isInteger(adcBits)) return param.bounds;
  const adcMax = 2 ** adcBits - 1;
  return { ...param.bounds, max: Math.min(param.bounds.max ?? Infinity, adcMax) };
}

/** Rango vigente como texto de ayuda (p. ej. "> 0" o "0–4095"). */
export function paramRange(param, adcBits = null) {
  return rangeText(paramBounds(param, adcBits));
}

/**
 * Interpreta lo escrito en el campo de `param`: el número, o `null` si no es un número finito, no
 * es entero cuando `param.integer`, o queda fuera del rango vigente. Acepta coma decimal.
 */
export function parseDraft(param, text, adcBits = null) {
  return parseNumber(text, { integer: param.integer, bounds: paramBounds(param, adcBits) });
}
