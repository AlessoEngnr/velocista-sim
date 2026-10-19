// Interpretación de lo que el usuario escribe en un campo numérico, con su rango. La usan las
// pestañas Ajuste y Calibración. Los rangos del panel son iguales o más estrictos que los del
// contrato, nunca más permisivos (FR-037; tests/browser/test_panel_ranges.py lo verifica).
//
// `bounds`: `min` (incluido), `above` (excluido: "> above") y `max` (incluido); cualquiera puede
// faltar.

/**
 * Devuelve el número escrito en `text` (acepta coma decimal), o `null` si no es un número finito,
 * si `integer` y no es entero, o si queda fuera de `bounds`.
 */
export function parseNumber(text, { integer = false, bounds = {} } = {}) {
  const trimmed = String(text).trim().replace(",", ".");
  if (!/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(trimmed)) return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value)) return null;
  if (integer && !Number.isInteger(value)) return null;
  const { min, above, max } = bounds;
  if (min !== undefined && value < min) return null;
  if (above !== undefined && value <= above) return null;
  if (max !== undefined && value > max) return null;
  return value;
}

/** Rango como texto de ayuda: "> 0", "≥ 1", "0–4095". */
export function rangeText({ min, above, max }) {
  if (min !== undefined && max !== undefined) return `${min}–${max}`;
  if (above !== undefined) return `> ${above}`;
  if (min !== undefined) return `≥ ${min}`;
  return max !== undefined ? `≤ ${max}` : "";
}
