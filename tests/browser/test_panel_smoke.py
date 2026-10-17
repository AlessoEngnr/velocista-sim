"""Prueba de humo del panel con Playwright (specs/003-panel-laboratorio, research R12).

Fase 2 (checkpoint): el panel abre su sesión en `/ws`, muestra `hello`/`config`, pide el
catálogo y todo frame cumple el contrato. Los casos de corrida (start → EN CORRIDA, resumen) se
agregan con US1 (T019).
"""

from __future__ import annotations

import json

from playwright.sync_api import Page, WebSocketRoute, expect

from support.browser import Capture, assert_frames_valid
from velocista_sim.contract import validate_message

HELLO = {
    "type": "hello", "v": 1, "t_ms": 0, "session_id": "s-falsa", "source": "sim",
    "robot": {"id": "velocista-01", "firmware": "sim-0.1", "hw_rev": "A"},
    "capabilities": {
        "line_sensors": 16, "adc_bits": 12, "motors": 2, "turbine": False, "encoders": False,
        "imu": False, "lap_timing": True, "battery": {"cells": 2, "nominal_v": 7.4, "voltage_sense": True},
    },
}
CONFIG = {
    "type": "config", "v": 1, "t_ms": 1, "controller": "pid",
    "params": {"kp": 0.045, "ki": 0, "kd": 0.9}, "base_speed": 180, "rate_hz": 50, "track_id": "oval-01",
}


def _by_id(page: Page, test_id: str):
    return page.get_by_test_id(test_id)


def test_panel_connects_and_shows_the_session(page: Page, capture: Capture, live_url: str) -> None:
    page.goto(live_url)

    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    expect(_by_id(page, "conn-status")).to_have_text("● CONECTADO")
    expect(_by_id(page, "robot-id")).to_have_text("velocista-01")
    expect(_by_id(page, "source")).to_have_text("sim")
    expect(_by_id(page, "rate-hz")).to_have_text("50 Hz")
    expect(_by_id(page, "track-id")).to_have_text("oval-01")
    expect(_by_id(page, "run-status")).to_have_attribute("data-state", "idle")
    expect(_by_id(page, "btn-reconnect")).to_be_hidden()
    expect(_by_id(page, "btn-start")).to_be_enabled()

    # Tras el primer `config` el panel pide el catálogo, y el servidor lo responde.
    _wait_for(lambda: any(m.get("type") == "catalog" for m in capture.received()), page)
    assert capture.sent() == [{"cmd": "list"}]
    assert capture.sockets and capture.sockets[0].endswith("/ws")

    assert_frames_valid(capture.frames)
    assert capture.console_errors == []


def test_rejected_set_config_and_set_rate_appear_in_the_log(page: Page, capture: Capture, live_url: str) -> None:
    """Los envíos de `set_config`/`set_rate` no se anotan en el registro, pero sus `error` sí."""
    errors = [
        {"type": "error", "v": 1, "t_ms": 2000, "code": "out_of_range", "cmd": "set_config",
         "message": "base_speed fuera de rango"},
        {"type": "error", "v": 1, "t_ms": 2500, "code": "out_of_range", "cmd": "set_rate",
         "message": "hz fuera de rango"},
    ]
    for message in (HELLO, CONFIG, *errors):
        assert validate_message(message, HELLO).ok, message

    def fake_server(ws: WebSocketRoute) -> None:
        for message in (HELLO, CONFIG, *errors):
            ws.send(json.dumps(message))

    page.route_web_socket("**/ws", fake_server)
    page.goto(live_url)

    log = _by_id(page, "log")
    expect(log.locator('li[data-kind="error"]')).to_have_count(2)
    expect(log.locator("li").nth(0)).to_contain_text("✕ out_of_range · set_rate · hz fuera de rango")
    expect(log.locator("li").nth(1)).to_contain_text("✕ out_of_range · set_config · base_speed fuera de rango")
    expect(log.locator("li").nth(0)).to_contain_text("2.500 s")
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    assert capture.console_errors == []


def _wait_for(condition, page: Page, timeout_ms: int = 5000) -> None:
    """Reintenta `condition` mientras la página procesa eventos (los frames llegan por callbacks)."""
    for _ in range(timeout_ms // 50):
        if condition():
            return
        page.wait_for_timeout(50)
    assert condition(), "la condición no se cumplió a tiempo"
