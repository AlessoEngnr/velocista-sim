"""Escenarios de aceptación de US1 por WebSocket con `TestClient` y reloj acelerado ×5 (research R10).

Cada mensaje recibido se valida con `ContractClient` (contrato + reglas de secuencia). Con el
reloj acelerado el núcleo va al máximo de CPU y la cola puede descartar `telemetry` (R11): esos
tests permiten saltos de `seq`; el de `seq` de a 1 usa el reloj real.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from support.contract_client import ContractClient, is_error, is_event, is_type
from support.session_driver import CONFIG_DIR
from velocista_sim.server.app import create_app
from velocista_sim.server.settings import Settings


class FastClock:
    """Reloj acelerado para el `Pacer`: `factor` segundos simulados por segundo real.

    ×5 y no ×20: con `TestClient` servidor y test comparten proceso y GIL, y un pacer siempre
    atrasado (al 100 % de CPU) deja sin turno al hilo del test. El resultado de la simulación
    no depende del reloj (principio VI).
    """

    def __init__(self, factor: float = 5.0) -> None:
        self.factor = factor
        self.origin = time.monotonic()

    def __call__(self) -> float:
        return (time.monotonic() - self.origin) * self.factor


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    app = create_app(Settings(config_dir=CONFIG_DIR), clock=FastClock())
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def realtime_client() -> Iterator[TestClient]:
    with TestClient(create_app(Settings(config_dir=CONFIG_DIR))) as test_client:
        yield test_client


@contextmanager
def session(client: TestClient, query: str = "", allow_drops: bool = True) -> Iterator[ContractClient]:
    with client.websocket_connect("/ws" + query) as websocket:
        yield ContractClient(websocket, allow_drops=allow_drops)


def _open(ws: ContractClient) -> tuple[dict, dict]:
    hello = ws.receive_json()
    config = ws.receive_json()
    return hello, config


def _slow_telemetry(ws: ContractClient) -> None:
    """10 Hz en corridas largas: menos validación compitiendo por el GIL con la simulación."""
    ws.send_cmd("set_rate", hz=10)
    assert ws.wait_for(is_type("config"))["rate_hz"] == 10


def test_opening_and_seq(realtime_client: TestClient) -> None:
    with session(realtime_client, allow_drops=False) as ws:
        hello, config = _open(ws)
        assert hello["type"] == "hello" and hello["source"] == "sim" and hello["t_ms"] == 0
        assert config["type"] == "config" and config["track_id"] == "oval-01" and config["t_ms"] == 0
        telemetry = [ws.wait_for(is_type("telemetry")) for _ in range(20)]
        assert [m["seq"] for m in telemetry] == list(range(20))
        assert all(m["running"] is False for m in telemetry)


def test_run_with_three_laps_and_stop(client: TestClient) -> None:
    with session(client) as ws:
        _open(ws)
        _slow_telemetry(ws)
        ws.send_cmd("set_config", params={"kp": 0.045, "kd": 0.9}, base_speed=180)
        config = ws.wait_for(is_type("config"))
        assert config["params"] == {"kp": 0.045, "ki": 0, "kd": 0.9}
        ws.send_cmd("start")
        started = ws.wait_for(is_event("run_started"))
        running = ws.wait_for(is_type("telemetry"))
        assert running["running"] is True and running["run_id"] == started["run_id"] and "lap" in running
        laps = [ws.wait_for(is_event("lap"))["lap"] for _ in range(3)]
        assert laps == [1, 2, 3]
        ws.send_cmd("stop")
        finished = ws.wait_for(is_event("run_finished"))
        assert finished["run_id"] == started["run_id"]
        assert finished["summary"]["laps"] >= 3 and finished["summary"]["off_tracks"] == 0
        # Después no llega otro run_finished (ContractClient lo verificaría) y sigue la telemetría.
        idle = ws.wait_for(lambda m: m["type"] == "telemetry" and not m["running"])
        assert "run_id" not in idle


def test_bad_config_goes_off_track(client: TestClient) -> None:
    with session(client) as ws:
        _open(ws)
        ws.send_cmd("set_config", params={"kp": 0})
        ws.wait_for(is_type("config"))
        ws.send_cmd("start")
        ws.wait_for(is_event("run_started"))
        off = ws.wait_for(is_event("off_track"))
        assert off["reason"] == "line_lost"
        finished = ws.receive_json()
        assert finished["event"] == "run_finished" and finished["summary"]["off_tracks"] == 1


def test_set_rate_list_and_reset(client: TestClient) -> None:
    with session(client) as ws:
        _open(ws)
        ws.send_cmd("set_rate", hz=20)
        assert ws.wait_for(is_type("config"))["rate_hz"] == 20
        first = ws.wait_for(is_type("telemetry"))
        second = ws.wait_for(is_type("telemetry"))
        assert second["t_ms"] - first["t_ms"] == 50
        ws.send_cmd("list")
        catalog = ws.wait_for(is_type("catalog"))
        assert catalog["robots"] == ["velocista-01"] and catalog["tracks"] == ["oval-01"]
        ws.send_cmd("reset")
        ws.send_cmd("stop")
        error = ws.wait_for(is_type("error"))
        assert error["code"] == "no_run"  # reset no respondió nada antes


def test_state_errors(client: TestClient) -> None:
    with session(client) as ws:
        _open(ws)
        ws.send_cmd("start")
        ws.wait_for(is_event("run_started"))
        ws.send_cmd("start")
        assert ws.wait_for(is_type("error"))["code"] == "run_active"
        ws.send_cmd("reset")
        assert ws.wait_for(is_type("error"))["code"] == "run_active"
        ws.send_cmd("stop")
        ws.wait_for(is_event("run_finished"))
        ws.send_cmd("stop")
        assert ws.wait_for(is_type("error"))["code"] == "no_run"


@pytest.mark.parametrize("frame, code", [("esto no es json", "invalid_json"),
                                         ('{"cmd": "volar"}', "unknown_cmd"),
                                         ('{"cmd": "start", "v": 2}', "unsupported_version"),
                                         ('{"cmd": "set_rate", "hz": 150}', "out_of_range"),
                                         ('{"cmd": "set_config", "base_speed": 1.5}', "invalid_params")])
def test_invalid_frames_do_not_close_the_session(client: TestClient, frame: str, code: str) -> None:
    with session(client) as ws:
        _open(ws)
        ws.send_text(frame)
        error = ws.wait_for(is_type("error"))
        assert error["code"] == code
        ws.send_cmd("list")
        assert ws.wait_for(is_type("catalog"))


def test_binary_frame_is_invalid_json(client: TestClient) -> None:
    with session(client) as ws:
        _open(ws)
        ws.websocket.send_bytes(b"\xff\x00")
        assert ws.wait_for(is_error("invalid_json"))


def test_sessions_are_independent(client: TestClient) -> None:
    with session(client) as first, session(client) as second:
        _open(first)
        _, config_second = _open(second)
        first.send_cmd("set_config", base_speed=150)
        first.wait_for(is_type("config"))
        first.send_cmd("start")
        first.wait_for(is_event("run_started"))
        first.wait_for(lambda m: m["type"] == "telemetry" and m["running"])
        for _ in range(20):
            message = second.wait_for(is_type("telemetry"))
            assert message["running"] is False
        second.send_cmd("list")
        second.wait_for(is_type("catalog"))
        assert [m for m in second.messages if m["type"] == "config"] == [config_second]
        assert not [m for m in second.messages if m["type"] == "event"]
        assert first.messages[0]["session_id"] != second.messages[0]["session_id"]
