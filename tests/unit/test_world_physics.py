"""Física diferencial: motores de primer orden, agarre lateral y batería (research R4, R13)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from velocista_sim.contract import effective_profile
from velocista_sim.world import WorldParams
from velocista_sim.world.physics import PhysicsState, battery_voltage, normalize_angle, step_physics

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE = REPO_ROOT / "config" / "robots" / "velocista-01.json"
DT = 0.002


@pytest.fixture(scope="module")
def params() -> WorldParams:
    return WorldParams.from_effective(effective_profile(json.loads(PROFILE.read_text(encoding="utf-8"))))


def test_first_order_motor(params: WorldParams) -> None:
    state = PhysicsState()
    pwm = 128
    v_cmd = pwm / 255 * params.max_speed_mps
    decay = math.exp(-DT / (params.motor_tau_ms / 1000))
    for n in range(1, 301):
        step_physics(state, pwm, pwm, params, DT)
        assert state.v_left == pytest.approx(v_cmd * (1 - decay**n), rel=1e-9)
    assert state.v_left == pytest.approx(v_cmd, rel=1e-5)


def test_equal_pwm_goes_straight(params: WorldParams) -> None:
    state = PhysicsState(x=1.0, y=1.0, theta=0.0)
    for _ in range(200):
        step_physics(state, 150, 150, params, DT)
    assert state.theta == pytest.approx(0.0, abs=1e-12)
    assert state.y == pytest.approx(1.0, abs=1e-12)
    assert state.x > 1.0


def test_pwm_difference_turns(params: WorldParams) -> None:
    state = PhysicsState(v_left=0.2, v_right=0.3)
    step_physics(state, 0, 0, params, DT)
    expected = (state.v_right - state.v_left) / params.wheelbase_m
    assert state.omega == pytest.approx(expected)
    assert state.theta == pytest.approx(expected * DT)
    assert state.omega > 0  # rueda derecha más rápida: giro a la izquierda


def test_lateral_grip_limit(params: WorldParams) -> None:
    state = PhysicsState(v_left=2.0, v_right=2.8)
    step_physics(state, 200, 255, params, DT)
    speed = (state.v_left + state.v_right) / 2
    asked = (state.v_right - state.v_left) / params.wheelbase_m
    assert abs(speed * asked) > params.max_lateral_accel_mps2
    assert abs(speed * state.omega) == pytest.approx(params.max_lateral_accel_mps2)
    assert math.copysign(1, state.omega) == math.copysign(1, asked)


def test_theta_normalized_and_distance_grows(params: WorldParams) -> None:
    state = PhysicsState()
    previous = 0.0
    for _ in range(3000):
        step_physics(state, -120, 120, params, DT)
        assert -math.pi < state.theta <= math.pi
        assert state.distance_m >= previous
        previous = state.distance_m
    backwards = PhysicsState()
    for _ in range(100):
        step_physics(backwards, -100, -100, params, DT)
    assert backwards.x < 0 and backwards.distance_m == pytest.approx(-backwards.x)


def test_normalize_angle() -> None:
    assert normalize_angle(math.pi) == pytest.approx(math.pi)
    assert normalize_angle(-math.pi) == pytest.approx(math.pi)
    assert normalize_angle(3 * math.pi / 2) == pytest.approx(-math.pi / 2)


@pytest.mark.parametrize("left, right", [(0, 0), (255, 255), (-255, 100), (180, 120)])
def test_battery(left: int, right: int) -> None:
    assert battery_voltage(7.4, left, right) == round(7.4 - 0.25 * (abs(left) + abs(right)) / 510, 3)
