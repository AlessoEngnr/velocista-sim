"""Escenarios de aceptación de US2 por WebSocket: `load`, `set_profile`, `load_track` y parámetros de conexión.

Cada mensaje recibido se valida con `ContractClient` contra el último `hello` (también el que
llega tras un `load`).
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from support.contract_client import ContractClient, is_error, is_event, is_type
from support.session_driver import CONFIG_DIR, oval_small_track
from velocista_sim.server.app import create_app
from velocista_sim.server.settings import Settings


class FastClock:
    """Reloj ×5 (ver tests/integration/test_ws_session.py)."""

    def __init__(self, factor: float = 5.0) -> None:
        self.factor = factor
        self.origin = time.monotonic()

    def __call__(self) -> float:
        return (time.monotonic() - self.origin) * self.factor


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app(Settings(config_dir=CONFIG_DIR), clock=FastClock())) as test_client:
        yield test_client


@contextmanager
def session(client: TestClient, query: str = "") -> Iterator[ContractClient]:
    with client.websocket_connect("/ws" + query) as websocket:
        yield ContractClient(websocket, allow_drops=True)


def _open(ws: ContractClient) -> tuple[dict, dict]:
    return ws.receive_json(), ws.receive_json()


def _next_non_telemetry(ws: ContractClient) -> dict:
    return ws.wait_for(lambda m: m["type"] != "telemetry")


def test_unknown_connection_parameters(client: TestClient) -> None:
    with session(client, "?robot=no-existe&track=no-existe") as ws:
        hello, config = _open(ws)
        assert hello["robot"]["id"] == "velocista-01" and config["track_id"] == "oval-01"
        assert _next_non_telemetry(ws)["code"] == "unknown_robot"
        assert _next_non_telemetry(ws)["code"] == "unknown_track"
        ws.send_cmd("list")
        assert ws.wait_for(is_type("catalog"))


def test_known_connection_parameters(client: TestClient) -> None:
    with session(client, "?robot=velocista-01&track=oval-01") as ws:
        hello, config = _open(ws)
        assert hello["robot"]["id"] == "velocista-01" and config["track_id"] == "oval-01"
        assert ws.wait_for(lambda m: m["type"] != "telemetry" or m["seq"] >= 3)["type"] == "telemetry"


def test_load_resends_hello_then_config(client: TestClient) -> None:
    with session(client) as ws:
        first_hello, _ = _open(ws)
        ws.send_cmd("set_rate", hz=25)
        ws.wait_for(is_type("config"))
        ws.send_cmd("load", robot_id="velocista-01")
        hello = _next_non_telemetry(ws)
        config = ws.receive_json()
        assert hello["type"] == "hello" and hello["session_id"] == first_hello["session_id"]
        assert config["type"] == "config" and config["rate_hz"] == 25
        assert ws.checker.hello is hello
        ws.send_cmd("load", robot_id="otro-robot")
        assert ws.wait_for(is_type("error"))["code"] == "unknown_robot"


def test_set_profile(client: TestClient) -> None:
    with session(client) as ws:
        _open(ws)
        ws.send_cmd("set_profile", measured={"wheelbase_m": 0.128})
        assert _next_non_telemetry(ws)["type"] == "config"
        ws.send_cmd("set_profile", measured={"line_sensors": 8})
        error = ws.wait_for(is_type("error"))
        assert (error["code"], error["cmd"]) == ("invalid_params", "set_profile")
        ws.send_cmd("set_profile", measured={"wheelbase_m": -0.1})
        assert ws.wait_for(is_type("error"))["code"] == "out_of_range"


def test_load_track_and_run_on_it(client: TestClient) -> None:
    with session(client) as ws:
        _open(ws)
        ws.send_cmd("load_track", track=oval_small_track())
        config = _next_non_telemetry(ws)
        assert config["type"] == "config" and config["track_id"] == "oval-small"
        ws.send_cmd("list")
        assert ws.wait_for(is_type("catalog"))["tracks"] == ["oval-01", "oval-small"]
        ws.send_cmd("set_rate", hz=10)
        ws.wait_for(is_type("config"))
        ws.send_cmd("start")
        ws.wait_for(is_event("run_started"))
        ws.wait_for(is_event("lap"))
        ws.send_cmd("load_track", track=oval_small_track())
        assert ws.wait_for(is_type("error"))["code"] == "run_active"
        ws.send_cmd("stop")
        summary = ws.wait_for(is_event("run_finished"))["summary"]
        assert summary["track_id"] == "oval-small" and summary["laps"] >= 1


def test_invalid_track(client: TestClient) -> None:
    with session(client) as ws:
        _open(ws)
        bad = oval_small_track()
        bad["units"] = "cm"
        ws.send_cmd("load_track", track=bad)
        error = ws.wait_for(is_type("error"))
        assert (error["code"], error["cmd"]) == ("invalid_track", "load_track")


def test_sim_only_commands_rejected_during_run(client: TestClient) -> None:
    with session(client) as ws:
        _open(ws)
        ws.send_cmd("start")
        ws.wait_for(is_event("run_started"))
        for cmd, fields in [("load", {"robot_id": "velocista-01"}),
                            ("set_profile", {"measured": {"adc_noise": 0}}),
                            ("reset", {})]:
            ws.send_cmd(cmd, **fields)
            error = ws.wait_for(is_type("error"))
            assert (error["code"], error["cmd"]) == ("run_active", cmd)


def test_quickstart_section_3_sequence(client: TestClient) -> None:
    """Secuencia de quickstart §3: respuestas en orden."""
    with session(client) as ws:
        _open(ws)
        frames = [
            ("list", {}),
            ("set_profile", {"measured": {"wheelbase_m": 0.128}}),
            ("set_profile", {"measured": {"line_sensors": 8}}),
            ("load", {"robot_id": "velocista-01"}),
            ("load", {"robot_id": "no-existe"}),
            ("start", {}),
            ("reset", {}),
            ("stop", {}),
        ]
        for cmd, fields in frames:
            ws.send_cmd(cmd, **fields)
        responses = [_next_non_telemetry(ws) for _ in range(9)]
        summary = [(m["type"], m.get("event") or m.get("code")) for m in responses]
        assert summary == [
            ("catalog", None), ("config", None), ("error", "invalid_params"), ("hello", None),
            ("config", None), ("error", "unknown_robot"), ("event", "run_started"),
            ("error", "run_active"), ("event", "run_finished"),
        ]
        assert responses[0]["robots"] == ["velocista-01"] and responses[0]["tracks"] == ["oval-01"]
        assert responses[2]["cmd"] == "set_profile" and responses[7]["cmd"] == "reset"

        ws.send_cmd("load_track", track=oval_small_track())
        assert _next_non_telemetry(ws)["track_id"] == "oval-small"
