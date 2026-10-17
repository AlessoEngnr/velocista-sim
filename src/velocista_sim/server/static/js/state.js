// Estado de la sesión del panel, solo en memoria de la pestaña (data-model.md, FR-036).
// `applyMessage(state, message)` es el único lugar donde se interpreta cada mensaje del
// contrato: un `case` por `type`. Las vistas solo leen este estado; `main.js` lo actualiza al
// llegar cada mensaje y marca `dirty` para que se redibuje en el siguiente cuadro.

const LOG_LIMIT = 50;

// Comandos que, si se aceptan, responden con `config` (research R5). Solo estos entran a la
// cola de pendientes; `start`, `stop`, `list` y `reset` no.
const PENDING_COMMANDS = new Set(["set_config", "set_rate", "set_profile", "load", "load_track"]);

/** Estado vacío de una pestaña recién abierta (forma de `PanelState`, data-model.md). */
export function createState() {
  return {
    connection: { status: "connecting", url: null, closeCode: null, sessionId: null },
    hello: null,
    caps: derived({ hello: null }),
    config: null,
    catalog: null,
    pending: [],
    telemetry: { last: null, lastSeq: null, lost: 0, received: 0 },
    run: null,
    trail: null,
    lapTarget: { value: null, stopSentFor: null },
    calibration: null,
    summaries: [],
    log: [],
    drafts: null,
    lastTMs: null,
    dirty: true,
  };
}

/** Banderas derivadas del `hello` que rigen qué se muestra (FR-006, FR-035). */
export function derived(state) {
  const capabilities = state.hello?.capabilities;
  return {
    isSim: state.hello?.source === "sim",
    sensorCount: capabilities?.line_sensors ?? 0,
    adcMax: capabilities ? 2 ** capabilities.adc_bits - 1 : 0,
    hasBattery: capabilities?.battery?.voltage_sense === true,
    hasLaps: capabilities?.lap_timing === true,
  };
}

/**
 * Aplica un mensaje del servidor al estado. Devuelve el pendiente que el mensaje resolvió
 * (`{ command, accepted }`) o `null`.
 */
export function applyMessage(state, message) {
  if (Number.isInteger(message?.t_ms)) state.lastTMs = message.t_ms;
  switch (message?.type) {
    // hello: datos del robot y capacidades. Reemplaza al anterior y recalcula los derivados.
    // Si llega tras un `load`, el pendiente lo resuelve el `config` que viene después.
    case "hello":
      state.hello = message;
      state.caps = derived(state);
      state.connection.sessionId = message.session_id;
      return null;

    // config: valores confirmados (fuente de verdad de los controles, FR-013). Resuelve como
    // aceptado el pendiente más antiguo; con la cola vacía (apertura de sesión) solo actualiza.
    case "config": {
      state.config = message;
      const command = state.pending.shift();
      return command ? { command, accepted: true } : null;
    }

    // catalog: listas de robots y pistas disponibles.
    case "catalog":
      state.catalog = message;
      return null;

    // error: se muestra en el registro. Con `cmd`, rechaza el pendiente más antiguo con ese
    // `cmd`; si no hay ninguno (o no trae `cmd`), la cola no cambia.
    case "error": {
      addLog(state, {
        kind: "error", tMs: message.t_ms, text: message.message, code: message.code, cmd: message.cmd ?? null,
      });
      if (!message.cmd) return null;
      const index = state.pending.findIndex((pending) => pending.cmd === message.cmd);
      if (index < 0) return null;
      const [command] = state.pending.splice(index, 1);
      return { command, accepted: false };
    }

    // telemetry / event: tipos del contrato que se interpretan con la historia US1 (T023);
    // mientras tanto se ignoran sin aviso.
    case "telemetry":
    case "event":
      return null;

    // Tipo desconocido: se ignora y se avisa en el registro.
    default:
      addLog(state, { kind: "warning", tMs: message?.t_ms ?? null, text: `Mensaje ignorado: tipo desconocido ${String(message?.type)}` });
      return null;
  }
}

/** Encola un comando enviado si es de los que responden con `config` (research R5). */
export function enqueuePending(state, command) {
  if (PENDING_COMMANDS.has(command.cmd)) state.pending.push({ cmd: command.cmd, payload: command });
}

/**
 * Agrega una entrada al registro, la más reciente primero, con tope de 50.
 * `kind` ∈ "event" | "error" | "local" | "warning". Sin `tMs`, toma el del último mensaje.
 */
export function addLog(state, entry) {
  state.log.unshift({
    kind: entry.kind,
    tMs: entry.tMs ?? state.lastTMs,
    text: entry.text,
    code: entry.code ?? null,
    cmd: entry.cmd ?? null,
  });
  if (state.log.length > LOG_LIMIT) state.log.length = LOG_LIMIT;
  state.dirty = true;
}

/**
 * Descarta la sesión anterior al reconectar (botón Reconectar o cambio de pista): todo vuelve a
 * su valor inicial, incluidos los resúmenes de corridas, menos el registro, que se conserva hasta
 * recargar la página (research R15).
 */
export function resetSession(state) {
  const log = state.log;
  Object.assign(state, createState());
  state.log = log;
}
