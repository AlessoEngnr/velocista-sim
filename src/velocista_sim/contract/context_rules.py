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
    if message.get("type") == "telemetry":
        return _sensor_violations(message, capabilities)
    return []


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


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
