"""Geometría de pista: longitud, poses, proyección y tramos con tinta (research R3, R9)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from velocista_sim.world import TrackGeometry

REPO_ROOT = Path(__file__).resolve().parents[2]
OVAL_01 = REPO_ROOT / "config" / "tracks" / "oval-01.json"
OVAL_SMALL = REPO_ROOT / "contract" / "examples" / "valid" / "commands" / "load_track" / "oval-small.json"


@pytest.fixture(scope="module")
def oval() -> TrackGeometry:
    return TrackGeometry.from_track(json.loads(OVAL_01.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def oval_small() -> TrackGeometry:
    track = json.loads(OVAL_SMALL.read_text(encoding="utf-8"))["message"]["track"]
    return TrackGeometry.from_track(track)


def _distance_to_ink(geometry: TrackGeometry, x: float, y: float) -> float:
    a, b = geometry.ink_a, geometry.ink_b
    ab = b - a
    t = np.clip(((np.array([x, y]) - a) * ab).sum(axis=1) / (ab * ab).sum(axis=1), 0, 1)
    closest = a + t[:, None] * ab
    return float(np.min(np.hypot(closest[:, 0] - x, closest[:, 1] - y)))


def test_oval_length_and_closed(oval: TrackGeometry) -> None:
    assert oval.closed
    assert oval.length == pytest.approx(3.0 + 2 * math.pi * 0.6, abs=0.001)
    assert oval.board == (3.0, 2.5)
    assert oval.line_width == pytest.approx(0.019)


def test_start_pose_on_bottom_straight_counterclockwise(oval: TrackGeometry) -> None:
    x, y, heading = oval.pose_at(oval.start_s)
    assert oval.start_s == pytest.approx(0.1)
    assert x == pytest.approx(0.85, abs=1e-6)
    assert y == pytest.approx(0.65, abs=1e-6)
    assert heading == pytest.approx(0.0, abs=1e-6)
    # Al terminar la recta inferior se gira a la izquierda (sentido antihorario).
    _, _, heading_curve = oval.pose_at(1.5 + 0.3)
    assert heading_curve > 0.3


@pytest.mark.parametrize("s", [0.0, 0.1, 1.2, 2.0, 3.3, 5.5, 6.7])
def test_project_point_on_line_returns_its_s(oval: TrackGeometry, s: float) -> None:
    x, y, _ = oval.pose_at(s)
    projected, index = oval.project(x, y)
    assert projected == pytest.approx(s, abs=1e-6)
    near, _ = oval.project(x, y, hint=index)
    assert near == pytest.approx(s, abs=1e-6)


def test_pose_wraps_on_closed_track(oval: TrackGeometry) -> None:
    assert oval.pose_at(oval.length + 0.5) == pytest.approx(oval.pose_at(0.5))


def test_gaps_have_no_ink(oval_small: TrackGeometry) -> None:
    gap_at, gap_length = 1.6, 0.02
    x, y, _ = oval_small.pose_at(gap_at + gap_length / 2)
    assert _distance_to_ink(oval_small, x, y) >= gap_length / 2 * 0.95
    x, y, _ = oval_small.pose_at(1.0)
    assert _distance_to_ink(oval_small, x, y) < 1e-9


def test_ink_candidates(oval: TrackGeometry) -> None:
    assert len(oval.ink_candidates((1.45, 1.20, 1.55, 1.30))) == 0
    x, y, _ = oval.pose_at(2.0)
    near = oval.ink_candidates((x - 0.01, y - 0.01, x + 0.01, y + 0.01))
    assert len(near) > 0
