"""Parámetros físicos que el mundo toma del perfil efectivo (contracts/world-robot.md)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class WorldParams:
    """Regleta, ADC, motores, chasis y batería del robot simulado."""

    line_sensors: int
    sensor_pitch_m: float
    sensor_offset_m: float
    adc_bits: int
    adc_white: int
    adc_black: int
    adc_noise: int
    max_speed_mps: float
    motor_tau_ms: float
    wheelbase_m: float
    max_lateral_accel_mps2: float
    battery_nominal_v: float

    @classmethod
    def from_effective(cls, effective: Mapping[str, object]) -> "WorldParams":
        """Construye los parámetros desde `effective_profile(perfil)`."""
        return cls(
            line_sensors=int(effective["line_sensors"]),
            sensor_pitch_m=float(effective["sensor_pitch_m"]),
            sensor_offset_m=float(effective["sensor_offset_m"]),
            adc_bits=int(effective["adc_bits"]),
            adc_white=int(effective["adc_white"]),
            adc_black=int(effective["adc_black"]),
            adc_noise=int(effective["adc_noise"]),
            max_speed_mps=float(effective["max_speed_mps"]),
            motor_tau_ms=float(effective["motor_tau_ms"]),
            wheelbase_m=float(effective["wheelbase_m"]),
            max_lateral_accel_mps2=float(effective["max_lateral_accel_mps2"]),
            battery_nominal_v=float(effective["battery_nominal_v"]),
        )
