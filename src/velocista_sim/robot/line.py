"""Posición de la línea a partir de las lecturas ADC (FR-018, research R7)."""

from __future__ import annotations

from typing import Sequence

from .params import RobotParams

NOISE_FLOOR = 0.1
LOST_THRESHOLD = 0.3


def line_position(sensors: Sequence[int], params: RobotParams, last_position: int) -> tuple[int, bool]:
    """Devuelve (`line_position` en milésimas de sensor, `line_lost`).

    Con la línea perdida devuelve el extremo del lado en que se vio por última vez.
    """
    span = params.adc_black - params.adc_white
    total = 0.0
    weighted = 0.0
    if span != 0:
        for index, value in enumerate(sensors):
            n = (value - params.adc_white) / span
            if n >= NOISE_FLOOR:
                n = 1.0 if n > 1.0 else n
                total += n
                weighted += index * n
    if total < LOST_THRESHOLD:
        center = (params.line_sensors - 1) * 500
        return (0 if last_position < center else (params.line_sensors - 1) * 1000), True
    return round(1000 * weighted / total), False


def line_error(position: int, line_sensors: int) -> int:
    """Error respecto del centro de la regleta: `line_position − (N − 1)·500`."""
    return position - (line_sensors - 1) * 500
