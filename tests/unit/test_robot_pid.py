"""PID a bordo y salida a motores (FR-017, FR-019, FR-020, research R7)."""

from __future__ import annotations

import pytest

from velocista_sim.robot import ControlOutput, PidConfig, Robot, RobotParams

PARAMS = RobotParams(line_sensors=16, adc_white=200, adc_black=3900, control_period_ms=2)
WHITE, BLACK = 200, 3900


def _at(index: int) -> list[int]:
    """Lecturas con la línea bajo el sensor `index` (posición index·1000)."""
    sensors = [WHITE] * 16
    sensors[index] = BLACK
    return sensors


def test_pid_terms() -> None:
    robot = Robot(PARAMS, PidConfig(kp=0.05, ki=0.001, kd=0.5, base_speed=150))
    first = robot.tick(_at(9), running=True)  # e = 1500
    assert first.error == 1500
    assert first.p == pytest.approx(0.05 * 1500)
    assert first.i == pytest.approx(0.001 * 1500)
    assert first.d == 0
    assert first.out == pytest.approx(first.p + first.i + first.d)
    assert first.left == round(150 + first.out) and first.right == round(150 - first.out)

    second = robot.tick(_at(10), running=True)  # e = 2500
    assert second.p == pytest.approx(0.05 * 2500)
    assert second.i == pytest.approx(0.001 * (1500 + 2500))
    assert second.d == pytest.approx(0.5 * 1000)


def test_reset_clears_state() -> None:
    robot = Robot(PARAMS, PidConfig(kp=0.0, ki=0.01, kd=1.0, base_speed=100))
    robot.tick(_at(3), running=True)
    robot.tick(_at(5), running=True)
    robot.reset()
    out = robot.tick(_at(12), running=True)
    assert out.d == 0
    assert out.i == pytest.approx(0.01 * 4500)


def test_motor_clipping() -> None:
    robot = Robot(PARAMS, PidConfig(kp=1.0, ki=0.0, kd=0.0, base_speed=200))
    out = robot.tick(_at(15), running=True)
    assert (out.left, out.right) == (255, -255)
    out = robot.tick(_at(0), running=True)
    assert (out.left, out.right) == (-255, 255)


def test_not_running_reports_line_but_no_control() -> None:
    robot = Robot(PARAMS, PidConfig(kp=0.045, ki=0.0, kd=0.9, base_speed=180))
    out = robot.tick(_at(11), running=False)
    assert out == ControlOutput(line_position=11000, line_lost=False, error=3500,
                                p=0, i=0, d=0, out=0, left=0, right=0)


def test_terms_are_bounded() -> None:
    robot = Robot(PARAMS, PidConfig(kp=1e300, ki=1e300, kd=1e300, base_speed=0))
    for index in (0, 15, 0, 15):
        out = robot.tick(_at(index), running=True)
        for value in (out.p, out.i, out.d, out.out):
            assert abs(value) <= 1e9
        assert -255 <= out.left <= 255 and -255 <= out.right <= 255


def test_set_config_applies_on_next_tick() -> None:
    robot = Robot(PARAMS, PidConfig(kp=0.0, ki=0.0, kd=0.0, base_speed=100))
    assert robot.tick(_at(9), running=True).left == 100
    robot.set_config(PidConfig(kp=0.01, ki=0.0, kd=0.0, base_speed=120))
    out = robot.tick(_at(9), running=True)
    assert out.left == round(120 + 15) and out.right == round(120 - 15)


def test_runs_every_step_with_default_period() -> None:
    assert PARAMS.control_period_ms == 2
    robot = Robot(PARAMS, PidConfig(kp=0.01, ki=0.0, kd=0.0, base_speed=100))
    outputs = [robot.tick(_at(i), running=True) for i in range(16)]
    assert [o.line_position for o in outputs] == [1000 * i for i in range(16)]
    assert robot.last_output == outputs[-1]
