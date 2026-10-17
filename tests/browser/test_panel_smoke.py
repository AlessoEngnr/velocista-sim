"""Prueba de humo del panel con Playwright (specs/003-panel-laboratorio, research R12).

Contra un uvicorn real: el panel abre su sesión, muestra `hello`/`config`, controla una corrida
(Iniciar → EN CORRIDA → Detener → resumen → Reiniciar) y todo frame cumple el contrato. Con un
servidor falso (`route_web_socket`): errores en el registro, vueltas objetivo y desconexión.
"""

from __future__ import annotations

from typing import Callable

from playwright.sync_api import Page, expect

from support.browser import Capture, assert_frames_valid
from support.fake_server import SIM_CONFIG, SIM_HELLO, FakeServer, event, open_session, telemetry


def _by_id(page: Page, test_id: str):
    return page.get_by_test_id(test_id)


def _wait_for(condition: Callable[[], bool], page: Page, timeout_ms: int = 5000) -> None:
    """Reintenta `condition` mientras la página procesa eventos (los frames llegan por callbacks)."""
    for _ in range(timeout_ms // 50):
        if condition():
            return
        page.wait_for_timeout(50)
    assert condition(), "la condición no se cumplió a tiempo"


def _seq(page: Page) -> int:
    return int(_by_id(page, "seq").text_content())


def _trail_points(page: Page) -> int:
    return int(_by_id(page, "trail-canvas").get_attribute("data-points"))


# --- Servidor real ---------------------------------------------------------------------------


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


def test_run_start_stop_and_reset(page: Page, capture: Capture, live_url: str) -> None:
    page.goto(live_url)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    expect(_by_id(page, "robot-id")).to_have_text("velocista-01")
    expect(_by_id(page, "run-status")).to_have_attribute("data-state", "idle")
    expect(_by_id(page, "btn-stop")).to_be_disabled()

    _by_id(page, "btn-start").click()
    expect(_by_id(page, "run-status")).to_have_attribute("data-state", "running")
    expect(_by_id(page, "run-status")).to_have_text("● EN CORRIDA")
    expect(_by_id(page, "run-id")).not_to_have_text("—")
    expect(_by_id(page, "btn-start")).to_be_disabled()

    first = _seq(page)
    _wait_for(lambda: _seq(page) > first, page)
    _wait_for(lambda: _trail_points(page) > 0, page)
    expect(_by_id(page, "pid-out")).not_to_have_text("—")
    expect(_by_id(page, "pwm-left")).to_contain_text("PWM")

    _by_id(page, "btn-stop").click()
    expect(_by_id(page, "summaries").locator("li")).to_have_count(1)
    expect(_by_id(page, "run-status")).to_have_attribute("data-state", "idle")

    _by_id(page, "btn-reset").click()
    _wait_for(lambda: {"cmd": "reset"} in capture.sent(), page)
    expect(_by_id(page, "trail-canvas")).to_have_attribute("data-points", "0")

    assert_frames_valid(capture.frames)
    assert capture.console_errors == []


# --- Servidor falso --------------------------------------------------------------------------


def test_rejected_set_config_and_set_rate_appear_in_the_log(page: Page, capture: Capture, live_url: str) -> None:
    """Los envíos de `set_config`/`set_rate` no se anotan en el registro, pero sus `error` sí."""
    errors = [
        {"type": "error", "v": 1, "t_ms": 2000, "code": "out_of_range", "cmd": "set_config",
         "message": "base_speed fuera de rango"},
        {"type": "error", "v": 1, "t_ms": 2500, "code": "out_of_range", "cmd": "set_rate",
         "message": "hz fuera de rango"},
    ]
    FakeServer(page, lambda connection: connection.send(SIM_HELLO, SIM_CONFIG, *errors))
    page.goto(live_url)

    log = _by_id(page, "log")
    expect(log.locator('li[data-kind="error"]')).to_have_count(2)
    expect(log.locator("li").nth(0)).to_contain_text("✕ out_of_range · set_rate · hz fuera de rango")
    expect(log.locator("li").nth(1)).to_contain_text("✕ out_of_range · set_config · base_speed fuera de rango")
    expect(log.locator("li").nth(0)).to_contain_text("2.500 s")
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    assert capture.console_errors == []


def _set_lap_target(page: Page, text: str) -> None:
    field = _by_id(page, "lap-target-input")
    field.fill(text)
    field.press("Enter")


def _run_laps(server: FakeServer, laps: int, extra_telemetry: int = 3) -> None:
    """La corrida `r-1`: arranque, `laps` vueltas y varias telemetrías con el último `lap.n`."""
    connection = server.last
    connection.send(event("run_started", "r-1", 2000), telemetry(SIM_HELLO, 1, run_id="r-1"))
    seq = 1
    for n in range(1, laps + 1):
        seq += 1
        connection.send(event("lap", "r-1", 2000 + n * 3000, lap=n, lap_ms=3000), telemetry(SIM_HELLO, seq, run_id="r-1", lap_n=n))
    for _ in range(extra_telemetry):
        seq += 1
        connection.send(telemetry(SIM_HELLO, seq, run_id="r-1", lap_n=laps))


def test_lap_target_sends_a_single_stop(page: Page, capture: Capture, live_url: str) -> None:
    server = FakeServer(page, open_session(SIM_HELLO, SIM_CONFIG))
    page.goto(live_url)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    _set_lap_target(page, "2")
    expect(_by_id(page, "lap-target-input")).not_to_have_attribute("aria-invalid", "true")

    _run_laps(server, 2, extra_telemetry=5)
    _wait_for(lambda: len(server.commands("stop")) == 1, page)
    expect(_by_id(page, "lap-target")).to_have_text(" / 2")
    page.wait_for_timeout(300)
    assert len(server.commands("stop")) == 1
    assert capture.console_errors == []


def test_empty_or_invalid_lap_target_never_stops(page: Page, capture: Capture, live_url: str) -> None:
    server = FakeServer(page, open_session(SIM_HELLO, SIM_CONFIG))
    page.goto(live_url)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")

    for text in ("0", "1.5"):
        _set_lap_target(page, text)
        expect(_by_id(page, "lap-target-input")).to_have_attribute("aria-invalid", "true")

    _run_laps(server, 3)
    expect(_by_id(page, "lap-n")).to_have_text("3")
    page.wait_for_timeout(300)
    assert server.commands("stop") == []

    _set_lap_target(page, "")
    expect(_by_id(page, "lap-target-input")).to_have_attribute("aria-invalid", "false")
    page.wait_for_timeout(200)
    assert server.commands("stop") == []
    assert capture.console_errors == []


def test_server_closing_shows_disconnected(page: Page, capture: Capture, live_url: str) -> None:
    server = FakeServer(page, open_session(SIM_HELLO, SIM_CONFIG))
    page.goto(live_url)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    server.last.close()
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "closed")
    expect(_by_id(page, "conn-status")).to_have_text("DESCONECTADO")
    expect(_by_id(page, "btn-reconnect")).to_be_visible()
    expect(_by_id(page, "btn-start")).to_be_disabled()
    expect(_by_id(page, "lap-target-input")).to_be_disabled()
    assert capture.console_errors == []


def test_full_server_then_reconnect(page: Page, capture: Capture, live_url: str) -> None:
    """Como el simulador con las sesiones al máximo: acepta y cierra con 1013 sin `hello`."""
    server = FakeServer(page)
    page.goto(live_url)
    _wait_for(lambda: len(server.connections) == 1, page)
    server.last.close(code=1013)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "closed")
    expect(page.locator('[data-role="conn-message"]')).to_contain_text("Servidor lleno")
    expect(_by_id(page, "btn-reconnect")).to_be_visible()

    _by_id(page, "btn-reconnect").click()
    _wait_for(lambda: len(server.connections) == 2, page)
    server.last.send(SIM_HELLO, SIM_CONFIG)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    expect(_by_id(page, "robot-id")).to_have_text("velocista-01")
    expect(_by_id(page, "btn-reconnect")).to_be_hidden()
    assert capture.console_errors == []
