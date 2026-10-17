// Barra superior: estado de la conexión, datos del robot y de la sesión, frecuencia y pista
// vigentes (FR-004, FR-005, FR-038, FR-039).

import { MISSING, formatHz } from "../format.js";
import { byTestId, setAttr, setHidden, setText } from "./dom.js";

const STATUS_TEXT = { connecting: "CONECTANDO", open: "● CONECTADO", closed: "DESCONECTADO" };

const CLOSE_MESSAGES = {
  1013: "Servidor lleno: no se pudo abrir la sesión. Reintentar más tarde",
  1008: "El servidor cerró la sesión porque el panel no leía a tiempo",
};

function yesNo(value) {
  return value ? "sí" : "no";
}

function capabilitiesText(capabilities) {
  if (!capabilities) return MISSING;
  const battery = capabilities.battery;
  const parts = [
    `${capabilities.line_sensors} sensores`,
    `ADC ${capabilities.adc_bits} bits`,
    `${capabilities.motors} motores`,
    `turbina ${yesNo(capabilities.turbine)}`,
    `encoders ${yesNo(capabilities.encoders)}`,
    `IMU ${yesNo(capabilities.imu)}`,
    `vueltas ${yesNo(capabilities.lap_timing)}`,
  ];
  if (battery) parts.push(`batería ${battery.cells}S ${battery.nominal_v} V (mide tensión: ${yesNo(battery.voltage_sense)})`);
  return parts.join(" · ");
}

/** Dibuja la barra superior con el estado actual. */
export function renderTopbar(root, state) {
  const { status, closeCode } = state.connection;
  const connStatus = byTestId(root, "conn-status");
  setText(connStatus, STATUS_TEXT[status]);
  setAttr(connStatus, "data-state", status);
  setHidden(byTestId(root, "btn-reconnect"), status !== "closed");
  const closeMessage = status === "closed" ? (CLOSE_MESSAGES[closeCode] ?? "") : "";
  setText(root.querySelector('[data-role="conn-message"]'), closeMessage);

  const hello = state.hello;
  setText(byTestId(root, "robot-id"), hello?.robot?.id ?? MISSING);
  setText(byTestId(root, "source"), hello?.source ?? MISSING);
  setText(byTestId(root, "session-id"), hello?.session_id ?? MISSING);
  setText(byTestId(root, "firmware"), hello?.robot?.firmware ?? MISSING);
  setText(byTestId(root, "hw-rev"), hello?.robot?.hw_rev ?? MISSING);
  setText(byTestId(root, "capabilities"), capabilitiesText(hello?.capabilities));

  setText(byTestId(root, "rate-hz"), formatHz(state.config?.rate_hz));
  setText(byTestId(root, "track-id"), state.config?.track_id ?? MISSING);
}
