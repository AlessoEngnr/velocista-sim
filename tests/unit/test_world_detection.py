"""Detección de vueltas y de salida de pista en el mundo (FR-013 a FR-015, research R9)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from velocista_sim.contract import effective_profile
from velocista_sim.world import LapCompleted, OffTrack, TrackGeometry, World, WorldParams

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE = REPO_ROOT / "config" / "robots" / "velocista-01.json"
OVAL_01 = REPO_ROOT / "config" / "tracks" / "oval-01.json"
DS = 0.005  # avance forzado por paso, m


@pytest.fixture(scope="module")
def params() -> WorldParams:
    return WorldParams.from_effective(effective_profile(json.loads(PROFILE.read_text(encoding="utf-8"))))


@pytest.fixture(scope="module")
def oval() -> TrackGeometry:
    return TrackGeometry.from_track(json.loads(OVAL_01.read_text(encoding="utf-8")))


def straight_track(gaps: list[dict]) -> TrackGeometry:
    return TrackGeometry.from_track({
        "id": "recta", "v": 1, "name": "recta", "units": "m",
        "board": {"width": 3.0, "height": 2.5}, "line_width": 0.019, "closed": False,
        "centerline": [[0.5 + 0.005 * i, 1.0] for i in range(301)],
        "gaps": gaps, "start": {"at": 0.05}, "rules_profile": "lgr2026",
    })


def _drive_along(world: World, track: TrackGeometry, s_from: float, s_to: float, t_ms: int):
    """Mueve la pose por la línea central de `s_from` a `s_to` y junta los eventos."""
    events = []
    steps = round(abs(s_to - s_from) / DS)
    direction = 1 if s_to >= s_from else -1
    for k in range(1, steps + 1):
        x, y, heading = track.pose_at(s_from + direction * k * DS)
        world.set_pose(x, y, heading)
        t_ms += 2
        events += [(t_ms, e) for e in world.detect(t_ms)]
    return events, t_ms


def test_lap_after_full_length(params: WorldParams, oval: TrackGeometry) -> None:
    world = World(params, oval)
    world.reset_to_start()
    world.begin_run(0)
    events, t_ms = _drive_along(world, oval, oval.start_s, oval.start_s + oval.length - 0.02, 0)
    assert events == []
    events, t_ms = _drive_along(world, oval, oval.start_s + oval.length - 0.02, oval.start_s + oval.length + 0.02, t_ms)
    laps = [(t, e) for t, e in events if isinstance(e, LapCompleted)]
    assert len(laps) == 1
    t_lap, lap = laps[0]
    assert lap == LapCompleted(lap=1, lap_ms=t_lap)
    assert not any(isinstance(e, OffTrack) for _, e in events)


def test_going_backwards_over_start_does_not_count(params: WorldParams, oval: TrackGeometry) -> None:
    world = World(params, oval)
    world.reset_to_start()
    world.begin_run(0)
    events, t_ms = _drive_along(world, oval, oval.start_s, oval.start_s - 0.5, 0)
    events2, _ = _drive_along(world, oval, oval.start_s - 0.5, oval.start_s + 0.2, t_ms)
    assert not any(isinstance(e, LapCompleted) for _, e in events + events2)


def test_stopped_without_ink_goes_off_after_one_second(params: WorldParams, oval: TrackGeometry) -> None:
    world = World(params, oval)
    world.reset_to_start()
    world.begin_run(0)
    world.set_pose(1.5, 1.25, 0.0)  # centro del óvalo: sin tinta cerca
    events = []
    t_ms = 0
    while not events and t_ms < 2000:
        t_ms += 2
        events = world.detect(t_ms)
    assert events == [OffTrack("line_lost")]
    assert 1000 < t_ms <= 1004


def test_driving_off_the_line_goes_off_after_ten_cm(params: WorldParams, oval: TrackGeometry) -> None:
    world = World(params, oval)
    world.set_pose(1.0, 1.0, 0.0)  # sobre el tablero, lejos de la línea
    world.begin_run(0)
    world.set_motor_pwm(200, 200)
    t_ms = 0
    events = []
    while not events and t_ms < 1000:
        world.step()
        t_ms += 2
        events = world.detect(t_ms)
    assert events == [OffTrack("line_lost")]
    assert world.truth()["distance_m"] == pytest.approx(0.10, abs=0.01)
    assert t_ms < 1000


def test_off_board_is_immediate(params: WorldParams, oval: TrackGeometry) -> None:
    world = World(params, oval)
    world.reset_to_start()
    world.begin_run(0)
    world.set_pose(-0.01, 0.65, 0.0)
    assert world.detect(2) == [OffTrack("line_lost")]


def test_crossing_a_short_gap_is_not_off_track(params: WorldParams) -> None:
    track = straight_track([{"at": 0.6, "length": 0.02}])
    world = World(params, track)
    world.reset_to_start()
    world.begin_run(0)
    world.set_motor_pwm(120, 120)
    t_ms = 0
    events = []
    bar_x = 0.0
    while not events and t_ms < 5000:
        world.step()
        t_ms += 2
        events = world.detect(t_ms)
        bar_x = world.truth()["x"] + params.sensor_offset_m
    assert events == [OffTrack("line_lost")]
    assert bar_x > 0.5 + 1.5  # salió recién al terminar la línea, no en el corte


def test_detect_without_run_is_silent(params: WorldParams, oval: TrackGeometry) -> None:
    world = World(params, oval)
    world.reset_to_start()
    world.set_pose(1.5, 1.25, 0.0)
    assert all(world.detect(2 * k) == [] for k in range(1, 1000))
