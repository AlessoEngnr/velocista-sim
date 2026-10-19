"""Servidor WebSocket falso para las pruebas de navegador, con `page.route_web_socket`
(research R14). Cada mensaje se valida con `validate_message` antes de enviarlo: el falso
servidor nunca manda algo que el contrato no permita (principio VII)."""

from __future__ import annotations

import copy
import json
import re
from typing import Callable

from playwright.sync_api import Page, WebSocketRoute

from velocista_sim.contract import validate_command, validate_message

SIM_HELLO = {
    "type": "hello", "v": 1, "t_ms": 0, "session_id": "s-falsa", "source": "sim",
    "robot": {"id": "velocista-01", "firmware": "sim-0.1", "hw_rev": "A"},
    "capabilities": {
        "line_sensors": 16, "adc_bits": 12, "motors": 2, "turbine": False, "encoders": False,
        "imu": False, "lap_timing": True, "battery": {"cells": 2, "nominal_v": 7.4, "voltage_sense": True},
    },
}
SIM_CONFIG = {
    "type": "config", "v": 1, "t_ms": 1, "controller": "pid",
    "params": {"kp": 0.045, "ki": 0, "kd": 0.9}, "base_speed": 180, "rate_hz": 50, "track_id": "oval-01",
}
ROBOT_HELLO = {
    **copy.deepcopy(SIM_HELLO),
    "session_id": "s-robot",
    "source": "robot",
    "robot": {"id": "velocista-01", "firmware": "esp32-0.1", "hw_rev": "A"},
}
ROBOT_HELLO["capabilities"]["lap_timing"] = False
ROBOT_HELLO["capabilities"]["battery"]["voltage_sense"] = False
ROBOT_CONFIG = {**SIM_CONFIG, "track_id": None}

SENSORS = [210, 198, 3870, 3912, 640, 205, 201, 199, 203, 197, 200, 204, 198, 202, 199, 201]


def telemetry(hello: dict, seq: int, *, run_id: str | None = None, lap_n: int = 0, t_ms: int | None = None) -> dict:
    """Telemetría válida para `hello`: con corrida si hay `run_id`; `lap`, `battery_v` y `sim_truth`
    solo cuando el contrato los pide."""
    capabilities = hello["capabilities"]
    message = {
        "type": "telemetry", "v": 1, "t_ms": t_ms if t_ms is not None else 1000 + seq * 20, "seq": seq,
        "running": run_id is not None, "sensors": SENSORS, "line_position": 7342, "line_lost": False,
        "error": -158, "control": {"p": -7.1, "i": 0, "d": 2.3, "out": -4.8},
        "motors": {"left": 172, "right": 128} if run_id else {"left": 0, "right": 0},
    }
    if run_id is not None:
        message["run_id"] = run_id
        if capabilities["lap_timing"]:
            message["lap"] = {"n": lap_n, "current_ms": 500}
    if capabilities["battery"]["voltage_sense"]:
        message["battery_v"] = 7.91
    if hello["source"] == "sim":
        message["sim_truth"] = {"x": 0.5 + seq * 0.01, "y": 0.45, "theta": 0.0, "speed_mps": 1.2, "distance_m": seq * 0.01}
    return message


def event(name: str, run_id: str, t_ms: int, **fields: object) -> dict:
    return {"type": "event", "v": 1, "t_ms": t_ms, "event": name, "run_id": run_id, **fields}


class FakeConnection:
    """Una conexión del panel al servidor falso."""

    def __init__(self, route: WebSocketRoute) -> None:
        self.route = route
        self.url = route.url
        self.hello: dict | None = None
        self.commands: list[dict] = []
        route.on_message(self._on_message)

    def _on_message(self, payload: str | bytes) -> None:
        command = json.loads(payload)
        result = validate_command(command)
        assert result.ok, f"el panel envió un comando inválido {command}: {result.violations}"
        self.commands.append(command)

    def send(self, *messages: dict) -> None:
        for message in messages:
            if message.get("type") == "hello":
                self.hello = message
            result = validate_message(message, self.hello)
            assert result.ok, f"el servidor falso iba a enviar un mensaje inválido {message}: {result.violations}"
            self.route.send(json.dumps(message))

    def close(self, code: int | None = None) -> None:
        if code is None:
            self.route.close()
        else:
            self.route.close(code=code)


class FakeServer:
    """Intercepta `/ws` de la página; `on_open(connection)` se llama en cada conexión nueva."""

    def __init__(self, page: Page, on_open: Callable[[FakeConnection], None] | None = None) -> None:
        self.connections: list[FakeConnection] = []
        self._on_open = on_open
        # `/ws` con o sin parámetros de conexión (`?track=&robot=`).
        page.route_web_socket(re.compile(r"/ws(\?.*)?$"), self._handle)

    def _handle(self, route: WebSocketRoute) -> None:
        connection = FakeConnection(route)
        self.connections.append(connection)
        if self._on_open:
            self._on_open(connection)

    @property
    def last(self) -> FakeConnection:
        assert self.connections, "el panel no abrió ninguna conexión"
        return self.connections[-1]

    def commands(self, cmd: str | None = None) -> list[dict]:
        sent = [c for connection in self.connections for c in connection.commands]
        return [c for c in sent if cmd is None or c["cmd"] == cmd]


def open_session(hello: dict, config: dict) -> Callable[[FakeConnection], None]:
    """`on_open` que manda `hello` y `config` al abrir, como el servidor real."""
    return lambda connection: connection.send(hello, config)
