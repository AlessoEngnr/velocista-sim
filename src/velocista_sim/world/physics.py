"""Tracción diferencial con motores de primer orden y límite de agarre (research R4, R13)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .params import WorldParams


@dataclass
class PhysicsState:
    """Pose verdadera y velocidades del robot (m, rad, m/s, rad/s)."""

    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0
    v_left: float = 0.0
    v_right: float = 0.0
    omega: float = 0.0
    distance_m: float = 0.0

    @property
    def speed(self) -> float:
        """Velocidad del eje, m/s."""
        return (self.v_left + self.v_right) / 2


def normalize_angle(theta: float) -> float:
    """Ángulo equivalente en (−π, π]."""
    wrapped = math.fmod(theta + math.pi, 2 * math.pi)
    if wrapped <= 0:
        wrapped += 2 * math.pi
    return wrapped - math.pi


def step_physics(state: PhysicsState, pwm_left: int, pwm_right: int, params: WorldParams, dt: float) -> None:
    """Avanza `state` un paso de `dt` segundos con los PWM dados."""
    gain = params.max_speed_mps / 255
    alpha = 1 - math.exp(-dt / (params.motor_tau_ms / 1000))
    state.v_left += (pwm_left * gain - state.v_left) * alpha
    state.v_right += (pwm_right * gain - state.v_right) * alpha

    speed = (state.v_left + state.v_right) / 2
    omega = (state.v_right - state.v_left) / params.wheelbase_m
    limit = params.max_lateral_accel_mps2
    if speed != 0 and abs(speed * omega) > limit:
        omega = math.copysign(limit / abs(speed), omega)
    state.omega = omega

    state.theta = normalize_angle(state.theta + omega * dt)
    state.x += speed * math.cos(state.theta) * dt
    state.y += speed * math.sin(state.theta) * dt
    state.distance_m += abs(speed) * dt


def battery_voltage(nominal_v: float, pwm_left: int, pwm_right: int) -> float:
    """Voltaje con una caída leve proporcional a la carga de los motores."""
    return round(nominal_v - 0.25 * (abs(pwm_left) + abs(pwm_right)) / 510, 3)
