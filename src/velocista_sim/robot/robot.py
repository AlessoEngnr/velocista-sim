"""Controlador a bordo: de lecturas ADC a PWM (FR-017 a FR-020, principio IV).

El robot no conoce la pista: solo recibe `sensors` y su propia calibración.
"""

from __future__ import annotations

from typing import Sequence

from .line import line_error, line_position
from .params import ControlOutput, PidConfig, RobotParams
from .pid import Pid

PWM_LIMIT = 255


def _clip_pwm(value: float) -> int:
    return max(-PWM_LIMIT, min(PWM_LIMIT, round(value)))


class Robot:
    """Calcula la línea y, con corrida activa, el PID y los PWM de cada motor."""

    def __init__(self, params: RobotParams, config: PidConfig) -> None:
        self.params = params
        self.config = config
        self.pid = Pid()
        self.last_position = (params.line_sensors - 1) * 500
        self.last_output = self._idle(self.last_position, False)

    def reset(self) -> None:
        """Reinicia integral, error previo y última posición vista."""
        self.pid.reset()
        self.last_position = (self.params.line_sensors - 1) * 500

    def set_config(self, config: PidConfig) -> None:
        self.config = config

    def set_params(self, params: RobotParams) -> None:
        self.params = params
        self.reset()

    def tick(self, sensors: Sequence[int], running: bool) -> ControlOutput:
        """Un tick de control. Sin corrida, el PID no corre: control y motores en 0."""
        position, lost = line_position(sensors, self.params, self.last_position)
        if not lost:
            self.last_position = position
        if not running:
            output = self._idle(position, lost)
        else:
            error = line_error(position, self.params.line_sensors)
            config = self.config
            p, i, d, out = self.pid.step(error, config.kp, config.ki, config.kd)
            output = ControlOutput(
                line_position=position, line_lost=lost, error=error, p=p, i=i, d=d, out=out,
                left=_clip_pwm(config.base_speed + out), right=_clip_pwm(config.base_speed - out),
            )
        self.last_output = output
        return output

    def _idle(self, position: int, lost: bool) -> ControlOutput:
        return ControlOutput(
            line_position=position, line_lost=lost,
            error=line_error(position, self.params.line_sensors),
            p=0, i=0, d=0, out=0, left=0, right=0,
        )
