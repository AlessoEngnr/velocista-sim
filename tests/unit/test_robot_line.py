"""Posición de línea a bordo: normalización, pérdida y error (FR-018, research R7)."""

from __future__ import annotations

import pytest

from velocista_sim.robot import RobotParams
from velocista_sim.robot.line import line_error, line_position

PARAMS = RobotParams(line_sensors=16, adc_white=200, adc_black=3900, control_period_ms=2)
WHITE, BLACK = 200, 3900


def _sensors(**values: int) -> list[int]:
    sensors = [WHITE] * 16
    for key, value in values.items():
        sensors[int(key[1:])] = value
    return sensors


def test_centered_line() -> None:
    position, lost = line_position(_sensors(s7=BLACK, s8=BLACK), PARAMS, 7500)
    assert (position, lost) == (7500, False)
    assert line_error(position, 16) == 0


def test_weighted_position() -> None:
    position, lost = line_position(_sensors(s2=BLACK, s3=(WHITE + BLACK) // 2), PARAMS, 7500)
    n3 = ((WHITE + BLACK) // 2 - WHITE) / (BLACK - WHITE)
    assert not lost
    assert position == round(1000 * (2 * 1 + 3 * n3) / (1 + n3))
    assert line_error(position, 16) == position - 7500


def test_noise_floor() -> None:
    small = WHITE + int(0.09 * (BLACK - WHITE))
    position, lost = line_position(_sensors(s0=small, s10=BLACK), PARAMS, 7500)
    assert (position, lost) == (10000, False)


def test_extremes_and_range() -> None:
    assert line_position(_sensors(s0=BLACK), PARAMS, 7500) == (0, False)
    assert line_position(_sensors(s15=BLACK), PARAMS, 7500) == (15000, False)
    for i in range(16):
        position, _ = line_position(_sensors(**{f"s{i}": BLACK}), PARAMS, 7500)
        assert 0 <= position <= 15000


@pytest.mark.parametrize("last, expected", [(3000, 0), (7499, 0), (7500, 15000), (12000, 15000)])
def test_lost_line_uses_last_side(last: int, expected: int) -> None:
    weak = WHITE + int(0.2 * (BLACK - WHITE))  # Σ n = 0,2 < 0,3
    assert line_position(_sensors(s5=weak), PARAMS, last) == (expected, True)
    assert line_position([WHITE] * 16, PARAMS, last) == (expected, True)


def test_values_outside_calibration_are_clipped() -> None:
    position, lost = line_position(_sensors(s4=65535, s5=0), PARAMS, 7500)
    assert (position, lost) == (4000, False)


def test_equal_calibration_means_no_line() -> None:
    params = RobotParams(line_sensors=16, adc_white=500, adc_black=500, control_period_ms=2)
    assert line_position([4000] * 16, params, 2000) == (0, True)
