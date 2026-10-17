"""Parámetros, configuración y salida del controlador a bordo (contracts/world-robot.md)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RobotParams:
    """Lo que el robot sabe de sí mismo: cantidad de sensores, calibración y periodo de control."""

    line_sensors: int
    adc_white: int
    adc_black: int
    control_period_ms: float


@dataclass(frozen=True)
class PidConfig:
    """Ganancias del PID y velocidad base (PWM 0–255)."""

    kp: float
    ki: float
    kd: float
    base_speed: int


@dataclass(frozen=True)
class ControlOutput:
    """Resultado de un tick de control; es lo que informa la telemetría."""

    line_position: int
    line_lost: bool
    error: int
    p: float
    i: float
    d: float
    out: float
    left: int
    right: int
