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


# --- Capacidades y paridad simulador–robot real -------------------------------------------


def _hello(source: str = "sim", **capabilities: object) -> dict:
    hello = copy.deepcopy(HELLO)
    hello["source"] = source
    voltage_sense = capabilities.pop("voltage_sense", None)
    if voltage_sense is not None:
        hello["capabilities"]["battery"]["voltage_sense"] = voltage_sense
    hello["capabilities"].update(capabilities)
    return hello


# Robot real sin capacidades opcionales: su telemetría no lleva battery_v, sim_truth ni lap.
ROBOT = _hello("robot", lap_timing=False, voltage_sense=False)
ODOMETRY = {"distance_m": 1.2, "speed_mps": 0.8, "heading_rad": 0.3}


def _robot_hello(**capabilities: object) -> dict:
    return _hello("robot", lap_timing=False, voltage_sense=False, **capabilities)


def _robot_telemetry(**changes: object) -> dict:
    message = _telemetry()
    del message["battery_v"], message["sim_truth"]
    message.update(changes)
    return message


def _running(message: dict) -> dict:
    return {**message, "running": True, "run_id": "r-0001"}


def test_robot_telemetry_without_optional_fields_is_valid() -> None:
    assert _rules(_robot_telemetry(), ROBOT) == set()
    assert _rules(_running(_robot_telemetry()), ROBOT) == set()


def test_odometry_without_capability() -> None:
    assert _rules(_robot_telemetry(odometry=ODOMETRY), ROBOT) == {
        ("odometry_without_capability", "/odometry")
    }


def test_odometry_without_capability_hides_field_rules() -> None:
    message = _robot_telemetry(odometry={"heading_rad": 0.3, "distance_m": 1.0})
    assert _rules(message, ROBOT) == {("odometry_without_capability", "/odometry")}


@pytest.mark.parametrize(
    ("encoders", "imu", "fields"),
    [
        (True, False, {"distance_m", "speed_mps"}),
        (False, True, {"heading_rad"}),
        (True, True, {"distance_m", "speed_mps", "heading_rad"}),
    ],
)
def test_odometry_with_exactly_its_fields_is_valid(encoders: bool, imu: bool, fields: set) -> None:
    odometry = {field: ODOMETRY[field] for field in fields}
    hello = _robot_hello(encoders=encoders, imu=imu)
    assert _rules(_robot_telemetry(odometry=odometry), hello) == set()


def test_odometry_encoder_fields() -> None:
    assert _rules(_robot_telemetry(odometry=ODOMETRY), _robot_hello(imu=True)) == {
        ("odometry_encoder_fields", "/odometry/distance_m"),
        ("odometry_encoder_fields", "/odometry/speed_mps"),
    }


def test_odometry_imu_fields() -> None:
    assert _rules(_robot_telemetry(odometry=ODOMETRY), _robot_hello(encoders=True)) == {
        ("odometry_imu_fields", "/odometry/heading_rad")
    }


@pytest.mark.parametrize(("encoders", "imu"), [(True, False), (False, True), (True, True)])
def test_odometry_missing_hides_field_rules(encoders: bool, imu: bool) -> None:
    hello = _robot_hello(encoders=encoders, imu=imu)
    assert _rules(_robot_telemetry(), hello) == {("odometry_missing", "/odometry")}


def test_odometry_encoder_fields_missing() -> None:
    message = _robot_telemetry(odometry={"speed_mps": 0.8})
    assert _rules(message, _robot_hello(encoders=True)) == {
        ("odometry_encoder_fields_missing", "/odometry/distance_m")
    }


def test_odometry_imu_fields_missing() -> None:
    message = _robot_telemetry(odometry={"distance_m": 1.2, "speed_mps": 0.8})
    assert _rules(message, _robot_hello(encoders=True, imu=True)) == {
        ("odometry_imu_fields_missing", "/odometry/heading_rad")
    }


def test_battery_without_sense() -> None:
    assert _rules(_robot_telemetry(battery_v=7.9), ROBOT) == {("battery_without_sense", "/battery_v")}


def test_battery_v_missing() -> None:
    message = _telemetry()
    del message["battery_v"]
    assert _rules(message) == {("battery_v_missing", "/battery_v")}


def test_sim_truth_without_sim() -> None:
    message = _robot_telemetry(sim_truth=TELEMETRY["sim_truth"])
    assert _rules(message, ROBOT) == {("sim_truth_without_sim", "/sim_truth")}


def test_sim_truth_missing() -> None:
    message = _telemetry()
    del message["sim_truth"]
    assert _rules(message) == {("sim_truth_missing", "/sim_truth")}


def test_lap_without_timing_in_telemetry() -> None:
    message = _running(_robot_telemetry(lap={"n": 0, "current_ms": 10}))
    assert _rules(message, ROBOT) == {("lap_without_timing", "/lap")}


def test_lap_missing() -> None:
    assert _rules(_running(_telemetry())) == {("lap_missing", "/lap")}
    assert _rules(_running(_telemetry(lap={"n": 0, "current_ms": 10}))) == set()


def test_lap_not_required_without_run() -> None:
    # Con lap_timing = true pero running = false no se exige lap (el schema incluso lo prohíbe).
    assert HELLO["capabilities"]["lap_timing"] is True
    assert _rules(_telemetry(running=False)) == set()


EVENT = {"type": "event", "v": 1, "t_ms": 2000, "run_id": "r-0001"}
SUMMARY = {
    "laps": 2, "best_lap_ms": 3400, "avg_lap_ms": 3450, "off_tracks": 0, "track_id": None,
    "config": {"controller": "pid", "params": {"kp": 0.04, "ki": 0, "kd": 0.9}, "base_speed": 180},
    "config_changed": False,
}
NO_LAP_TIMES = {"best_lap_ms": None, "avg_lap_ms": None}


def _run_finished(**summary: object) -> dict:
    return {**EVENT, "event": "run_finished", "summary": {**SUMMARY, **summary}}


def test_lap_without_timing_in_event() -> None:
    message = {**EVENT, "event": "lap", "lap": 1, "lap_ms": 3400}
    assert _rules(message) == set()
    assert _rules(message, ROBOT) == {("lap_without_timing", "/event")}


def test_summary_laps_without_timing() -> None:
    assert _rules(_run_finished(), ROBOT) == {
        ("summary_laps_without_timing", "/summary/laps"),
        ("summary_laps_without_timing", "/summary/best_lap_ms"),
        ("summary_laps_without_timing", "/summary/avg_lap_ms"),
    }
    assert _rules(_run_finished(laps=0, **NO_LAP_TIMES), ROBOT) == {
        ("summary_laps_without_timing", "/summary/laps")
    }
    assert _rules(_run_finished(laps=None, **NO_LAP_TIMES), ROBOT) == set()


def test_summary_laps_missing() -> None:
    assert _rules(_run_finished(laps=None, **NO_LAP_TIMES)) == {("summary_laps_missing", "/summary/laps")}
    assert _rules(_run_finished(laps=0, **NO_LAP_TIMES)) == set()


def _catalog(robots: list, tracks: list) -> dict:
    return {"type": "catalog", "v": 1, "t_ms": 10, "robots": robots, "tracks": tracks}


def test_catalog_robot_real() -> None:
    assert _rules(_catalog(["mini-8"], []), ROBOT) == set()
    assert _rules(_catalog(["mini-8", "otro"], ["oval-01"]), ROBOT) == {
        ("catalog_robot_real", "/robots"),
        ("catalog_robot_real", "/tracks"),
    }
    assert _rules(_catalog(["mini-8", "otro"], ["oval-01"])) == set()


def test_track_id_robot_real() -> None:
    config = {
        "type": "config", "v": 1, "t_ms": 5, "controller": "pid",
        "params": {"kp": 0.04, "ki": 0, "kd": 0.9}, "base_speed": 180, "rate_hz": 50,
        "track_id": "oval-01",
    }
    assert _rules(config) == set()
    assert _rules(config, ROBOT) == {("track_id_robot_real", "/track_id")}
    assert _rules({**config, "track_id": None}, ROBOT) == set()


def test_same_telemetry_depends_on_last_hello() -> None:
    # Tras un load llega un hello nuevo: el mismo telemetry pasa a validarse con él.
    message = _robot_telemetry(odometry={"distance_m": 1.2, "speed_mps": 0.8})
    assert _rules(message, ROBOT) == {("odometry_without_capability", "/odometry")}
    assert _rules(message, _robot_hello(encoders=True)) == set()
