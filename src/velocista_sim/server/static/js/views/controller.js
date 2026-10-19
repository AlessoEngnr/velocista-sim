// Tarjetas Controlador y Motores: términos del PID y comandos PWM (FR-016).

import { formatPid, formatPwm } from "../format.js";
import { byTestId, setText } from "./dom.js";

/** Dibuja PID y PWM con la última telemetría. */
export function renderController(root, state) {
  const telemetry = state.telemetry.last;
  setText(byTestId(root, "pid-p"), formatPid(telemetry?.control.p));
  setText(byTestId(root, "pid-i"), formatPid(telemetry?.control.i));
  setText(byTestId(root, "pid-d"), formatPid(telemetry?.control.d));
  setText(byTestId(root, "pid-out"), formatPid(telemetry?.control.out));
  setText(byTestId(root, "pwm-left"), formatPwm(telemetry?.motors.left));
  setText(byTestId(root, "pwm-right"), formatPwm(telemetry?.motors.right));
}
