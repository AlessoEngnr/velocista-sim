"""Valor efectivo del perfil del robot (FR-035)."""

from __future__ import annotations

from conftest import EXAMPLES_DIR, read_json
from velocista_sim.contract import effective_profile


def _wheelbase(measured: float | None) -> dict:
    return {"wheelbase_m": {"default": 0.130, "measured": measured, "source": "estimated"}}


def test_uses_default_without_measured() -> None:
    assert effective_profile(_wheelbase(None)) == {"wheelbase_m": 0.130}


def test_measured_overrides_default() -> None:
    # Escenario US3-3: set_profile con measured.wheelbase_m = 0.128.
    assert effective_profile(_wheelbase(0.128)) == {"wheelbase_m": 0.128}


def test_falsy_measured_values_still_override() -> None:
    profile = {
        "turbine": {"default": True, "measured": False, "source": "current_robot"},
        "adc_noise": {"default": 60, "measured": 0, "source": "estimated"},
    }
    assert effective_profile(profile) == {"turbine": False, "adc_noise": 0}


def test_default_profile_example() -> None:
    profile = read_json(EXAMPLES_DIR / "valid" / "robot-profile" / "velocista-01-default.json")["message"]
    effective = effective_profile(profile)
    assert len(effective) == len(profile) == 25
    assert effective["wheelbase_m"] == 0.130
    assert effective["line_sensors"] == 16
    assert effective["turbine_suction_n"] is None


def test_with_measured_example() -> None:
    profile = read_json(EXAMPLES_DIR / "valid" / "robot-profile" / "with-measured.json")["message"]
    assert effective_profile(profile)["wheelbase_m"] == 0.128
