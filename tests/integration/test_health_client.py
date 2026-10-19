"""`/health`, límite de sesiones y `examples/client.py` contra un uvicorn real (US3, FR-042, FR-043)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from support.live_server import free_port, start_live_server
from support.session_driver import CONFIG_DIR
from velocista_sim.server.app import create_app
from velocista_sim.server.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT = REPO_ROOT / "examples" / "client.py"


def _settings(**fields: object) -> Settings:
    return Settings(config_dir=CONFIG_DIR, **fields)


# --- /health y límite de sesiones con TestClient --------------------------------------------


def test_health_ok() -> None:
    with TestClient(create_app(_settings(max_sessions=5))) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "sessions": 0, "max_sessions": 5}
        with client.websocket_connect("/ws") as websocket:
            websocket.receive_text()
            assert client.get("/health").json()["sessions"] == 1


def test_full_server_rejects_with_1013() -> None:
    with TestClient(create_app(_settings(max_sessions=1))) as client:
        with client.websocket_connect("/ws") as first:
            first.receive_text()
            response = client.get("/health")
            assert response.status_code == 503
            assert response.json() == {"status": "full", "sessions": 1, "max_sessions": 1}
            with client.websocket_connect("/ws") as second:
                with pytest.raises(WebSocketDisconnect) as closed:
                    second.receive_text()
                assert closed.value.code == 1013
        assert client.get("/health").json() == {"status": "ok", "sessions": 0, "max_sessions": 1}


def test_disconnect_during_run_frees_the_session() -> None:
    with TestClient(create_app(_settings())) as client:
        with client.websocket_connect("/ws") as websocket:
            websocket.receive_text()
            websocket.send_text('{"cmd": "start"}')
            while '"run_started"' not in websocket.receive_text():
                pass
        assert client.get("/health").json()["sessions"] == 0


# --- examples/client.py contra uvicorn real -------------------------------------------------


@pytest.fixture(scope="module")
def server_url() -> Iterator[str]:
    with start_live_server(_settings()) as http_url:
        yield http_url.replace("http://", "ws://", 1) + "/ws"


def _run_client(*args: str) -> subprocess.CompletedProcess[str]:
    """Corre el cliente con el intérprete del venv de dev (ya tiene websockets), nunca con `uv run`."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, str(CLIENT), *args], capture_output=True, text=True, encoding="utf-8",
        timeout=60, env=env,
    )


def test_client_prints_summary(server_url: str) -> None:
    result = _run_client(server_url, "--laps", "1", "--timeout", "20")
    assert result.returncode == 0, result.stderr
    assert "hello:" in result.stdout and "config:" in result.stdout
    assert "event lap 1" in result.stdout
    assert "laps (vueltas): 1" in result.stdout
    assert "off_tracks (salidas de pista): 0" in result.stdout


def test_client_bad_config_goes_off_track(server_url: str) -> None:
    result = _run_client(server_url, "--kp", "0", "--kd", "0", "--timeout", "20")
    assert result.returncode == 0, result.stderr
    assert "event off_track" in result.stdout
    assert "off_tracks (salidas de pista): 1" in result.stdout


def test_client_rejected_config_exits_2(server_url: str) -> None:
    result = _run_client(server_url, "--base-speed", "300")
    assert result.returncode == 2
    assert "out_of_range" in result.stdout + result.stderr


def test_client_without_server_exits_1() -> None:
    result = _run_client(f"ws://127.0.0.1:{free_port()}/ws", "--timeout", "5")
    assert result.returncode == 1
    assert "No se pudo conectar" in result.stderr
