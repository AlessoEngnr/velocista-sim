"""Semántica de la pista track v1 (data-model.md § Capa 3)."""

from __future__ import annotations

import pytest

from velocista_sim.contract import validate_command, validate_track


def _straight(count: int = 201, x0: float = 0.5, y: float = 0.5) -> list[list[float]]:
    return [[round(x0 + i * 0.005, 6), y] for i in range(count)]


def _square(side_points: int = 100, x0: float = 0.5, y0: float = 0.5) -> list[list[float]]:
    """Cuadrado cerrado de 0,5 m de lado, recorrido en sentido antihorario cada 5 mm."""
    side = side_points * 0.005
    points = []
    for i in range(side_points):
        points.append([x0 + i * 0.005, y0])
    for i in range(side_points):
        points.append([x0 + side, y0 + i * 0.005])
    for i in range(side_points):
        points.append([x0 + side - i * 0.005, y0 + side])
    for i in range(side_points):
        points.append([x0, y0 + side - i * 0.005])
    return [[round(x, 6), round(y, 6)] for x, y in points]


def _track(**changes: object) -> dict:
    track = {
        "id": "test", "v": 1, "name": "Prueba", "units": "m",
        "board": {"width": 3.0, "height": 2.5}, "line_width": 0.019, "closed": False,
        "centerline": _straight(), "gaps": [], "start": {"at": 0.0}, "rules_profile": "lgr2026",
    }
    track.update(changes)
    return track


def _rules(track: dict) -> set[tuple[str, str]]:
    return {(v.rule, v.path) for v in validate_track(track).violations}


def test_open_straight_of_one_meter_is_valid() -> None:
    assert _rules(_track(start={"at": 1.0}, gaps=[{"at": 0.5, "length": 0.02}])) == set()


def test_closed_square_is_valid() -> None:
    # Longitud 2 m: el tramo de cierre cuenta para la longitud, no para el muestreo.
    track = _track(closed=True, centerline=_square(), start={"at": 1.999})
    assert _rules(track) == set()


def test_closing_segment_counts_for_length_only_when_closed() -> None:
    square = _square()
    assert _rules(_track(closed=True, centerline=square, start={"at": 2.0})) == set()
    assert _rules(_track(closed=False, centerline=square, start={"at": 2.0})) == {
        ("track_at_range", "/start/at")
    }


@pytest.mark.parametrize(("start", "gap_at"), [(1.01, 0.5), (0.0, 1.2)])
def test_at_range(start: float, gap_at: float) -> None:
    track = _track(start={"at": start}, gaps=[{"at": gap_at, "length": 0.02}])
    expected = ("/start/at",) if start > 1.0 else ("/gaps/0/at",)
    assert _rules(track) == {("track_at_range", path) for path in expected}


def test_point_outside_board() -> None:
    centerline = _straight(x0=2.5)  # termina en x = 3,5 m, fuera de un tablero de 3 m
    outside = {
        ("track_point_outside_board", f"/centerline/{i}")
        for i, (x, _) in enumerate(centerline)
        if x > 3.0
    }
    assert outside
    assert _rules(_track(centerline=centerline)) == outside


def test_gaps_overlap() -> None:
    gaps = [{"at": 0.30, "length": 0.05}, {"at": 0.60, "length": 0.02}, {"at": 0.34, "length": 0.02}]
    assert _rules(_track(gaps=gaps)) == {("track_gaps_overlap", "/gaps/2")}


def test_adjacent_gaps_do_not_overlap() -> None:
    gaps = [{"at": 0.30, "length": 0.05}, {"at": 0.35, "length": 0.05}]
    assert _rules(_track(gaps=gaps)) == set()


def test_sampling() -> None:
    centerline = _straight()
    del centerline[10]
    assert _rules(_track(centerline=centerline)) == {("track_sampling", "/centerline/10")}


def test_sampling_tolerance_is_ten_percent() -> None:
    ok = [[0.5, 0.5], [0.50549, 0.5], [0.51, 0.5]]   # 5,49 mm y 4,51 mm
    bad = [[0.5, 0.5], [0.50556, 0.5], [0.51, 0.5]]  # 5,56 mm y 4,44 mm
    assert _rules(_track(centerline=ok)) == set()
    assert _rules(_track(centerline=bad)) == {
        ("track_sampling", "/centerline/1"),
        ("track_sampling", "/centerline/2"),
    }


def test_semantic_rules_need_schema_to_pass() -> None:
    track = _track(units="cm", start={"at": 5.0})
    assert _rules(track) == {("const", "/units")}


def test_load_track_prefixes_paths_with_track() -> None:
    result = validate_command({"cmd": "load_track", "track": _track(start={"at": 5.0})})
    assert {(v.rule, v.path) for v in result.violations} == {("track_at_range", "/track/start/at")}
