"""Capa 3: semántica de la pista track v1 (data-model.md § Capa 3).

Se aplica solo a pistas que ya pasaron la capa de schema.
"""

from __future__ import annotations

import math

from .result import Violation

SAMPLING_M = 0.005
SAMPLING_TOLERANCE = 0.10


def track_violations(track: dict) -> list[Violation]:
    """Violaciones semánticas de `track`: posiciones `at`, tablero, cortes y muestreo."""
    points: list[list[float]] = track["centerline"]
    steps = [math.dist(a, b) for a, b in zip(points, points[1:])]
    length = sum(steps)
    if track["closed"]:
        length += math.dist(points[-1], points[0])

    violations: list[Violation] = []
    violations += _at_violations(track, length)
    violations += _board_violations(points, track["board"])
    violations += _gap_violations(track["gaps"])
    violations += _sampling_violations(steps)
    return violations


def _at_violations(track: dict, length: float) -> list[Violation]:
    positions = [("/start/at", track["start"]["at"])]
    positions += [(f"/gaps/{index}/at", gap["at"]) for index, gap in enumerate(track["gaps"])]
    return [
        Violation(
            "track_at_range", path,
            f"at vale {at} m y debe estar entre 0 y la longitud de centerline ({length:.4f} m)",
        )
        for path, at in positions
        if not 0 <= at <= length
    ]


def _board_violations(points: list[list[float]], board: dict) -> list[Violation]:
    width, height = board["width"], board["height"]
    return [
        Violation(
            "track_point_outside_board", f"/centerline/{index}",
            f"el punto {index} ({x}, {y}) está fuera del tablero [0, {width}] × [0, {height}]",
        )
        for index, (x, y) in enumerate(points)
        if not (0 <= x <= width and 0 <= y <= height)
    ]


def _gap_violations(gaps: list[dict]) -> list[Violation]:
    violations: list[Violation] = []
    for index, gap in enumerate(gaps):
        start, end = gap["at"], gap["at"] + gap["length"]
        for previous_index, previous in enumerate(gaps[:index]):
            if start < previous["at"] + previous["length"] and previous["at"] < end:
                violations.append(Violation(
                    "track_gaps_overlap", f"/gaps/{index}",
                    f"el corte {index} se superpone con el corte {previous_index}",
                ))
                break
    return violations


def _sampling_violations(steps: list[float]) -> list[Violation]:
    low = SAMPLING_M * (1 - SAMPLING_TOLERANCE)
    high = SAMPLING_M * (1 + SAMPLING_TOLERANCE)
    return [
        Violation(
            "track_sampling", f"/centerline/{index}",
            f"el punto {index} está a {step * 1000:.2f} mm del anterior; se esperan 5 mm ± 10 %",
        )
        for index, step in enumerate(steps, start=1)
        if not low <= step <= high
    ]
