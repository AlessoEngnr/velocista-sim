"""Capa 2: reglas que dependen del `hello` de la sesión (data-model.md § Capa 2).

Se aplican solo a mensajes que ya pasaron la capa de schema.
"""

from __future__ import annotations

from typing import Any

from .result import Violation


def context_violations(message: dict, hello: dict) -> list[Violation]:
    """Violaciones de `message` en el contexto de `hello` (el último de la sesión)."""
    capabilities = hello.get("capabilities")
    if not isinstance(capabilities, dict):
        return []
    context = _Context(hello, capabilities)
    match message.get("type"):
        case "telemetry":
            return (
                _sensor_violations(message, capabilities)
                + _odometry_violations(message, context)
                + _presence_violations(message, context)
            )
        case "event":
            return _event_violations(message, context)
        case "catalog":
            return _catalog_violations(message, context)
        case "config":
            return _config_violations(message, context)
    return []


class _Context:
    """Lo que el `hello` declara, leído una sola vez."""

    def __init__(self, hello: dict, capabilities: dict) -> None:
        battery = capabilities.get("battery")
        robot = hello.get("robot")
        self.source = hello.get("source")
        self.robot_id = robot.get("id") if isinstance(robot, dict) else None
        self.encoders = capabilities.get("encoders") is True
        self.imu = capabilities.get("imu") is True
        self.lap_timing = capabilities.get("lap_timing") is True
        self.voltage_sense = isinstance(battery, dict) and battery.get("voltage_sense") is True


def _sensor_violations(telemetry: dict, capabilities: dict) -> list[Violation]:
    violations: list[Violation] = []
    line_sensors = capabilities.get("line_sensors")
    adc_bits = capabilities.get("adc_bits")
    sensors: list[Any] = telemetry["sensors"]

    if _is_int(line_sensors) and len(sensors) != line_sensors:
        violations.append(Violation(
            "sensors_length", "/sensors",
            f"sensors trae {len(sensors)} valores y capabilities.line_sensors es {line_sensors}",
        ))

    if _is_int(adc_bits):
        adc_max = 2**adc_bits - 1
        for index, value in enumerate(sensors):
            if value > adc_max:
                violations.append(Violation(
                    "sensor_range", f"/sensors/{index}",
                    f"el sensor {index} vale {value} y con adc_bits = {adc_bits}, el máximo es {adc_max}",
                ))

    if _is_int(line_sensors):
        line_position = telemetry["line_position"]
        position_max = (line_sensors - 1) * 1000
        if line_position > position_max:
            violations.append(Violation(
                "line_position_range", "/line_position",
                f"line_position vale {line_position} y con {line_sensors} sensores el máximo es "
                f"{position_max}",
            ))
        center = (line_sensors - 1) * 500
        expected_error = line_position - center
        if telemetry["error"] != expected_error:
            violations.append(Violation(
                "error_consistency", "/error",
                f"error vale {telemetry['error']} y debe ser line_position − {center} = "
                f"{expected_error}",
            ))

    return violations


def _odometry_violations(telemetry: dict, context: _Context) -> list[Violation]:
    odometry = telemetry.get("odometry")
    if not (context.encoders or context.imu):
        if odometry is None:
            return []
        return [Violation(
            "odometry_without_capability", "/odometry",
            "odometry llega pero hello no declara encoders ni imu",
        )]
    if odometry is None:
        return [Violation(
            "odometry_missing", "/odometry", "falta odometry y hello declara encoders o imu",
        )]

    violations: list[Violation] = []
    for field in ("distance_m", "speed_mps"):
        path = f"/odometry/{field}"
        if context.encoders and field not in odometry:
            violations.append(Violation(
                "odometry_encoder_fields_missing", path,
                f"falta odometry.{field} y hello declara encoders",
            ))
        elif not context.encoders and field in odometry:
            violations.append(Violation(
                "odometry_encoder_fields", path, f"odometry.{field} llega sin encoders declarados",
            ))
    if context.imu and "heading_rad" not in odometry:
        violations.append(Violation(
            "odometry_imu_fields_missing", "/odometry/heading_rad",
            "falta odometry.heading_rad y hello declara imu",
        ))
    elif not context.imu and "heading_rad" in odometry:
        violations.append(Violation(
            "odometry_imu_fields", "/odometry/heading_rad",
            "odometry.heading_rad llega sin imu declarada",
        ))
    return violations


def _presence_violations(telemetry: dict, context: _Context) -> list[Violation]:
    """Campos de `telemetry` presentes si y solo si se cumple su condición (FR-018)."""
    violations: list[Violation] = []

    if context.voltage_sense and "battery_v" not in telemetry:
        violations.append(Violation(
            "battery_v_missing", "/battery_v",
            "falta battery_v y hello declara capabilities.battery.voltage_sense = true",
        ))
    elif not context.voltage_sense and "battery_v" in telemetry:
        violations.append(Violation(
            "battery_without_sense", "/battery_v",
            "battery_v llega pero hello declara capabilities.battery.voltage_sense = false",
        ))

    if context.source == "sim" and "sim_truth" not in telemetry:
        violations.append(Violation(
            "sim_truth_missing", "/sim_truth", 'falta sim_truth y hello declara source = "sim"',
        ))
    elif context.source == "robot" and "sim_truth" in telemetry:
        violations.append(Violation(
            "sim_truth_without_sim", "/sim_truth",
            'sim_truth es solo-sim y hello declara source = "robot"',
        ))

    if not context.lap_timing and "lap" in telemetry:
        violations.append(Violation(
            "lap_without_timing", "/lap", "el bloque lap llega pero hello declara lap_timing = false",
        ))
    elif context.lap_timing and telemetry["running"] and "lap" not in telemetry:
        violations.append(Violation(
            "lap_missing", "/lap",
            "falta el bloque lap durante una corrida y hello declara lap_timing = true",
        ))

    return violations


def _event_violations(event: dict, context: _Context) -> list[Violation]:
    if event["event"] == "lap" and not context.lap_timing:
        return [Violation(
            "lap_without_timing", "/event", "event lap llega pero hello declara lap_timing = false",
        )]
    if event["event"] != "run_finished":
        return []

    summary = event["summary"]
    if context.lap_timing:
        if summary["laps"] is None:
            return [Violation(
                "summary_laps_missing", "/summary/laps",
                "summary.laps es null y hello declara lap_timing = true",
            )]
        return []
    return [
        Violation(
            "summary_laps_without_timing", f"/summary/{field}",
            f"summary.{field} debe ser null porque hello declara lap_timing = false",
        )
        for field in ("laps", "best_lap_ms", "avg_lap_ms")
        if summary[field] is not None
    ]


def _catalog_violations(catalog: dict, context: _Context) -> list[Violation]:
    if context.source != "robot":
        return []
    violations: list[Violation] = []
    if catalog["robots"] != [context.robot_id]:
        violations.append(Violation(
            "catalog_robot_real", "/robots",
            f"el robot real responde robots = [{context.robot_id!r}], solo con su propio id",
        ))
    if catalog["tracks"] != []:
        violations.append(Violation(
            "catalog_robot_real", "/tracks", "el robot real responde tracks = []",
        ))
    return violations


def _config_violations(config: dict, context: _Context) -> list[Violation]:
    if context.source == "robot" and config["track_id"] is not None:
        return [Violation(
            "track_id_robot_real", "/track_id", "el robot real envía track_id = null",
        )]
    return []


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
