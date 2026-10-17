// Estado de la sesión del panel, solo en memoria de la pestaña (data-model.md, FR-036).
// `applyMessage(state, message)` es el único lugar donde se interpreta cada mensaje del
// contrato: un `case` por `type`. Las vistas solo leen este estado; `main.js` lo actualiza al
// llegar cada mensaje y marca `dirty` para que se redibuje en el siguiente cuadro.

import { formatSeconds } from "./format.js";
import { clearTrail, createTrail, pushPoint } from "./trail.js";

const LOG_LIMIT = 50;
const LAPS_LIMIT = 100;
const SUMMARIES_LIMIT = 50;

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
    lastRun: null,          // la última corrida terminada, para la tarjeta Vueltas
    finishedRunId: null,    // evita revivir con telemetría atrasada una corrida ya terminada
    trail: createTrail(),
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
    // hello: datos del robot y capacidades. Reemplaza al anterior, recalcula los derivados y
    // limpia el rastro. Si llega tras un `load`, el pendiente lo resuelve el `config` siguiente.
    case "hello":
      state.hello = message;
      state.caps = derived(state);
      state.connection.sessionId = message.session_id;
      clearTrail(state.trail);
      return null;

    // config: valores confirmados (fuente de verdad de los controles, FR-013). Resuelve como
    // aceptado el pendiente más antiguo; con la cola vacía (apertura de sesión) solo actualiza.
    case "config": {
      state.config = message;
      const command = state.pending.shift();
      return command ? { command, accepted: true } : null;
    }

    // telemetry: última lectura, saltos de `seq` (FR-019), punto del rastro y estado de corrida.
    case "telemetry":
      applyTelemetry(state, message);
      return null;

    // event: corrida, vueltas, salidas de pista y resúmenes; todos quedan en el registro.
    case "event":
      applyEvent(state, message);
      return null;

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

    // Tipo desconocido: se ignora y se avisa en el registro.
    default:
      addLog(state, { kind: "warning", tMs: message?.t_ms ?? null, text: `Mensaje ignorado: tipo desconocido ${String(message?.type)}` });
      return null;
  }
}

function applyTelemetry(state, message) {
  const telemetry = state.telemetry;
  if (telemetry.lastSeq !== null) {
    const gap = message.seq - telemetry.lastSeq - 1;
    if (gap > 0) telemetry.lost += gap;
  }
  telemetry.lastSeq = message.seq;
  telemetry.last = message;
  telemetry.received += 1;

  // El rastro es el recorrido de la corrida: fuera de corrida solo se mueve la pose, para que
  // Reiniciar deje el rastro vacío aunque la telemetría en reposo siga trayendo `sim_truth`.
  const truth = message.sim_truth;
  if (truth) {
    if (message.running) pushPoint(state.trail, truth.x, truth.y, truth.theta);
    else state.trail.pose = { x: truth.x, y: truth.y, theta: truth.theta };
  }

  // Si se perdió `run_started` o `run_finished`, la telemetría manda (data-model.md, ObservedRun).
  if (message.running && message.run_id && message.run_id !== state.run?.runId
      && message.run_id !== state.finishedRunId) {
    startRun(state, message.run_id);
  } else if (!message.running && state.run) {
    state.run = null;
  }
}

function startRun(state, runId) {
  state.run = { runId, laps: [], bestLapMs: null, lastLapMs: null, avgLapMs: null, offTracks: [] };
  state.lastRun = null;
}

function applyEvent(state, message) {
  switch (message.event) {
    case "run_started":
      if (state.run?.runId !== message.run_id) startRun(state, message.run_id);
      addLog(state, { kind: "event", tMs: message.t_ms, text: `▶ corrida ${message.run_id} iniciada` });
      break;

    case "lap": {
      if (state.run?.runId !== message.run_id) startRun(state, message.run_id);
      const run = state.run;
      run.laps.unshift({ n: message.lap, lapMs: message.lap_ms });
      if (run.laps.length > LAPS_LIMIT) run.laps.length = LAPS_LIMIT;
      run.lastLapMs = message.lap_ms;
      run.bestLapMs = Math.min(...run.laps.map((lap) => lap.lapMs));
      run.avgLapMs = Math.round(run.laps.reduce((sum, lap) => sum + lap.lapMs, 0) / run.laps.length);
      addLog(state, { kind: "event", tMs: message.t_ms, text: `vuelta ${message.lap} · ${formatSeconds(message.lap_ms)}` });
      break;
    }

    case "off_track":
      state.run?.offTracks.push({ tMs: message.t_ms, reason: message.reason });
      addLog(state, { kind: "event", tMs: message.t_ms, text: `✕ FUERA DE PISTA (${message.reason})` });
      break;

    case "run_finished": {
      state.summaries.unshift({ run_id: message.run_id, t_ms: message.t_ms, ...message.summary });
      if (state.summaries.length > SUMMARIES_LIMIT) state.summaries.length = SUMMARIES_LIMIT;
      state.lastRun = state.run?.runId === message.run_id ? state.run : null;
      state.run = null;
      state.finishedRunId = message.run_id;
      const laps = message.summary.laps === null ? "" : ` · ${message.summary.laps} vueltas`;
      addLog(state, { kind: "event", tMs: message.t_ms, text: `■ corrida ${message.run_id} terminada${laps}` });
      break;
    }

    default:
      addLog(state, { kind: "warning", tMs: message.t_ms, text: `Evento ignorado: ${String(message.event)}` });
  }
}

/** Vueltas completadas en la corrida activa, según `event lap` y `telemetry.lap.n`. */
export function completedLaps(state) {
  if (!state.run) return 0;
  const fromEvents = state.run.laps[0]?.n ?? 0;
  const last = state.telemetry.last;
  const fromTelemetry = last?.running && last.run_id === state.run.runId ? (last.lap?.n ?? 0) : 0;
  return Math.max(fromEvents, fromTelemetry);
}

/**
 * Fija las vueltas objetivo desde el texto del campo: vacío = sin límite, o un entero ≥ 1.
 * Devuelve si el texto es válido; si no lo es, el objetivo vigente no cambia (research R16).
 */
export function setLapTarget(state, text) {
  const trimmed = text.trim();
  if (trimmed === "") {
    state.lapTarget.value = null;
    return true;
  }
  if (!/^\d+$/.test(trimmed) || Number(trimmed) < 1) return false;
  state.lapTarget.value = Number(trimmed);
  return true;
}

/** `true` si hay que enviar el `stop` automático: objetivo alcanzado y aún no enviado. */
export function shouldAutoStop(state) {
  return state.run !== null
    && state.lapTarget.value !== null
    && completedLaps(state) >= state.lapTarget.value
    && state.lapTarget.stopSentFor !== state.run.runId;
}

/** Recuerda que la corrida activa ya recibió su `stop` automático (una sola vez por `run_id`). */
export function markAutoStop(state) {
  state.lapTarget.stopSentFor = state.run.runId;
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
 * su valor inicial, incluidos rastro, contadores de `seq` y resúmenes de corridas, menos el
 * registro, que se conserva hasta recargar la página (research R15).
 */
export function resetSession(state) {
  const log = state.log;
  Object.assign(state, createState());
  state.log = log;
}
