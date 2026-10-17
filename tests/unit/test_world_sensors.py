"""Lecturas ADC de la regleta: cobertura, ruido sembrado y cortes (FR-012, research R3)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import numpy as np
import pytest

from velocista_sim.contract import effective_profile
from velocista_sim.world import TrackGeometry, World, WorldParams
from velocista_sim.world.sensors import coverage, readings, sensor_positions

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE = REPO_ROOT / "config" / "robots" / "velocista-01.json"
OVAL_01 = REPO_ROOT / "config" / "tracks" / "oval-01.json"


def straight_track(gaps: list[dict] | None = None) -> dict:
    """Recta abierta de 1 m sobre y = 1,0 (de x = 0,5 a 1,5)."""
    return {
        "id": "recta", "v": 1, "name": "recta", "units": "m",
        "board": {"width": 3.0, "height": 2.5}, "line_width": 0.019, "closed": False,
        "centerline": [[0.5 + 0.005 * i, 1.0] for i in range(201)],
        "gaps": gaps or [], "start": {"at": 0.1}, "rules_profile": "lgr2026",
    }


@pytest.fixture(scope="module")
def params() -> WorldParams:
    return WorldParams.from_effective(effective_profile(json.loads(PROFILE.read_text(encoding="utf-8"))))


@pytest.fixture(scope="module")
def oval() -> TrackGeometry:
    return TrackGeometry.from_track(json.loads(OVAL_01.read_text(encoding="utf-8")))


def test_centered_on_straight(params: WorldParams, oval: TrackGeometry) -> None:
    world = World(params, oval)
    world.reset_to_start()
    values = world.read_sensors(np.random.default_rng(1))
    assert len(values) == params.line_sensors
    center = params.line_sensors // 2
    for index in (center - 1, center):
        assert abs(values[index] - params.adc_black) <= params.adc_noise + 40
    for index in (0, 1, params.line_sensors - 2, params.line_sensors - 1):
        assert abs(values[index] - params.adc_white) <= params.adc_noise
    assert all(isinstance(v, int) and 0 <= v <= 2**params.adc_bits - 1 for v in values)


def test_sensor_zero_is_on_the_left(params: WorldParams) -> None:
    points = sensor_positions(0.0, 0.0, 0.0, params)
    assert points.shape == (params.line_sensors, 2)
    assert points[0, 1] > 0 > points[-1, 1]
    assert points[:, 0] == pytest.approx(params.sensor_offset_m)
    assert points[0, 1] - points[1, 1] == pytest.approx(params.sensor_pitch_m)


@pytest.mark.parametrize("d", [0.0, 0.004, 0.006, 0.009, 0.012, 0.0142, 0.02])
def test_partial_coverage(params: WorldParams, d: float) -> None:
    geometry = TrackGeometry.from_track(straight_track())
    cov = coverage(np.array([[1.0, 1.0 + d]]), geometry, params)
    a = params.sensor_pitch_m
    expected = min(max((geometry.line_width / 2 + a / 2 - d) / a, 0.0), 1.0)
    assert cov[0] == pytest.approx(expected, abs=1e-9)


def test_intermediate_readings_without_noise(params: WorldParams) -> None:
    quiet = dataclasses.replace(params, adc_noise=0)
    geometry = TrackGeometry.from_track(straight_track())
    cov = coverage(np.array([[1.0, 1.0 + 0.012]]), geometry, quiet)
    value = readings(cov, quiet, np.random.default_rng(0))[0]
    assert quiet.adc_white < value < quiet.adc_black


def test_over_a_gap_everything_is_white(params: WorldParams) -> None:
    geometry = TrackGeometry.from_track(straight_track([{"at": 0.4, "length": 0.05}]))
    world = World(dataclasses.replace(params, adc_noise=0), geometry)
    world.set_pose(0.5 + 0.425 - params.sensor_offset_m, 1.0, 0.0)
    assert world.read_sensors(np.random.default_rng(0)) == [params.adc_white] * params.line_sensors
    assert not world.sees_ink()


def test_noise_is_seeded(params: WorldParams, oval: TrackGeometry) -> None:
    world = World(params, oval)
    world.reset_to_start()
    first = world.read_sensors(np.random.default_rng(7))
    second = world.read_sensors(np.random.default_rng(7))
    assert first == second
    assert first != world.read_sensors(np.random.default_rng(8))

    quiet = World(dataclasses.replace(params, adc_noise=0), oval)
    quiet.reset_to_start()
    assert quiet.read_sensors(np.random.default_rng(1)) == quiet.read_sensors(np.random.default_rng(2))


def test_readings_are_clipped(params: WorldParams) -> None:
    noisy = dataclasses.replace(params, adc_white=10, adc_black=4090, adc_noise=500)
    rng = np.random.default_rng(3)
    values = readings(np.array([0.0] * 8 + [1.0] * 8), noisy, rng)
    assert min(values) >= 0 and max(values) <= 4095
