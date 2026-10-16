"""Reglas contextuales de la capa 2 (data-model.md § Capa 2)."""

from __future__ import annotations

import copy

import pytest

from velocista_sim.contract import validate_message

# Robot de 8 sensores con ADC de 10 bits: centro 3500, máximo de sensor 1023.
HELLO = {
    "type": "hello", "v": 1, "t_ms": 0, "session_id": "s-test", "source": "sim",
    "robot": {"id": "mini-8", "firmware": "sim-0.1", "hw_rev": "A"},
    "capabilities": {
        "line_sensors": 8, "adc_bits": 10, "motors": 2, "turbine": False, "encoders": False,
        "imu": False, "lap_timing": True,
        "battery": {"cells": 2, "nominal_v": 7.4, "voltage_sense": True},
    },
}

TELEMETRY = {
    "type": "telemetry", "v": 1, "t_ms": 1000, "seq": 50, "running": False,
    "sensors": [100, 120, 900, 1023, 300, 110, 105, 100],
    "line_position": 3400, "line_lost": False, "error": -100,
    "control": {"p": -1.0, "i": 0, "d": 0.5, "out": -0.5},
    "motors": {"left": 0, "right": 0},
    "battery_v": 7.8,
    "sim_truth": {"x": 0.5, "y": 0.4, "theta": 0.0, "speed_mps": 0.0, "distance_m": 0.0},
}


def _telemetry(**changes: object) -> dict:
    message = copy.deepcopy(TELEMETRY)
    message.update(changes)
    return message


def _rules(message: dict, hello: dict | None = HELLO) -> set[tuple[str, str]]:
    return {(v.rule, v.path) for v in validate_message(message, hello).violations}


def test_valid_telemetry_with_context() -> None:
    result = validate_message(_telemetry(), HELLO)
    assert result.ok
    assert result.context_checked


@pytest.mark.parametrize("length", [7, 9])
def test_sensors_length(length: int) -> None:
    sensors = [100] * length
    assert _rules(_telemetry(sensors=sensors)) == {("sensors_length", "/sensors")}


def test_sensor_range_uses_adc_bits() -> None:
    sensors = [100, 120, 900, 1024, 300, 110, 1500, 100]
    assert _rules(_telemetry(sensors=sensors)) == {
        ("sensor_range", "/sensors/3"),
        ("sensor_range", "/sensors/6"),
    }


def test_sensor_at_adc_max_is_valid() -> None:
    assert _rules(_telemetry(sensors=[1023] * 8)) == set()


def test_line_position_range() -> None:
    assert _rules(_telemetry(line_position=7000, error=3500)) == set()
    assert _rules(_telemetry(line_position=7001, error=3501)) == {
        ("line_position_range", "/line_position")
    }


def test_error_consistency() -> None:
    assert _rules(_telemetry(line_position=3500, error=0)) == set()
    assert _rules(_telemetry(error=0)) == {("error_consistency", "/error")}


def test_context_rules_need_schema_to_pass() -> None:
    # Un mensaje que falla el schema no informa además reglas contextuales.
    message = _telemetry(sensors=[100] * 7)
    del message["seq"]
    assert _rules(message) == {("required", "/seq")}


def test_without_hello_context_is_not_checked() -> None:
    result = validate_message(_telemetry(sensors=[5000] * 3, error=0))
    assert result.ok
    assert not result.context_checked


def test_hello_is_its_own_context() -> None:
    result = validate_message(HELLO)
    assert result.ok
    assert result.context_checked


def test_violations_are_sorted_by_path_then_rule() -> None:
    message = _telemetry(sensors=[2000, 100, 100, 100, 100, 100, 100, 2000, 100], error=0)
    paths = [(v.path, v.rule) for v in validate_message(message, HELLO).violations]
    assert paths == sorted(paths)
    assert paths == [
        ("/error", "error_consistency"),
        ("/sensors", "sensors_length"),
        ("/sensors/0", "sensor_range"),
        ("/sensors/7", "sensor_range"),
    ]
