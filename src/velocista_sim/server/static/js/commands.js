// Constructores de los comandos del contrato v1 (contracts/client-protocol.md, FR-037).
// Es la ÚNICA vía para construir comandos en el panel: cada función es pura, devuelve el objeto
// a enviar como un frame de texto JSON y no tiene efectos. Los comandos no llevan `v` (es
// opcional) ni `t_ms`. Los tests construyen un ejemplo de cada función y lo validan contra el
// contrato con `validate_command`.

const GAINS = ["kp", "ki", "kd"];
const INTEGER_PROFILE_PARAMS = new Set(["adc_white", "adc_black", "adc_noise", "encoder_ticks_per_rev"]);

/** Inicia una corrida. */
export function start() {
  return { cmd: "start" };
}

/** Detiene la corrida activa. */
export function stop() {
  return { cmd: "stop" };
}

/** Vuelve el robot simulado a la posición de largada (solo simulador). */
export function reset() {
  return { cmd: "reset" };
}

/**
 * Cambia la configuración del controlador. Lleva solo los campos pasados:
 * `kp`, `ki`, `kd` van dentro de `params`; `base_speed` se redondea y se limita a 0–255.
 */
export function setConfig(fields) {
  const command = { cmd: "set_config" };
  const params = {};
  for (const key of GAINS) {
    if (fields[key] !== undefined) params[key] = Number(fields[key]);
  }
  if (Object.keys(params).length > 0) command.params = params;
  if (fields.base_speed !== undefined) {
    command.base_speed = Math.min(255, Math.max(0, Math.round(Number(fields.base_speed))));
  }
  return command;
}

/** Cambia la frecuencia de telemetría (10–100 Hz, entero). */
export function setRate(hz) {
  return { cmd: "set_rate", hz: Math.round(Number(hz)) };
}

/** Pide el catálogo de robots y pistas. */
export function list() {
  return { cmd: "list" };
}

/** Carga otro robot del catálogo (solo simulador). */
export function load(robotId) {
  return { cmd: "load", robot_id: robotId };
}

/**
 * Fija valores medidos del perfil (solo simulador). `null` borra el medido y vuelve al
 * default; los parámetros enteros del contrato se envían como enteros.
 */
export function setProfile(measured) {
  const values = {};
  for (const [key, value] of Object.entries(measured)) {
    if (value === null) values[key] = null;
    else values[key] = INTEGER_PROFILE_PARAMS.has(key) ? Math.round(Number(value)) : Number(value);
  }
  return { cmd: "set_profile", measured: values };
}

/** Carga una pista track v1 enviada por el cliente (solo simulador). Se envía tal cual. */
export function loadTrack(track) {
  return { cmd: "load_track", track };
}
