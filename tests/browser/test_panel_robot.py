"""El panel con un robot real simulado (SC-006, FR-035, research R14).

Un servidor falso hace de robot: `source = "robot"`, sin vueltas, sin sensor de batería y sin
`sim_truth`. Los elementos solo-sim se ocultan y el resto funciona igual (principio II).
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from support.browser import Capture
from support.fake_server import ROBOT_CONFIG, ROBOT_HELLO, FakeServer, open_session, telemetry


def _by_id(page: Page, test_id: str):
    return page.get_by_test_id(test_id)


def test_real_robot_hides_sim_only_elements(page: Page, capture: Capture, live_url: str) -> None:
    server = FakeServer(page, open_session(ROBOT_HELLO, ROBOT_CONFIG))
    page.goto(live_url)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    expect(_by_id(page, "source")).to_have_text("robot")
    expect(_by_id(page, "track-id")).to_have_text("—")

    # Telemetrías con un salto de seq: 1, 2, 3, 7 → se perdieron 4, 5 y 6 (FR-019).
    for seq in (1, 2, 3, 7):
        server.last.send(telemetry(ROBOT_HELLO, seq))
    expect(_by_id(page, "seq")).to_have_text("7")
    expect(_by_id(page, "seq-lost")).to_have_text("3")

    for test_id in ("btn-reset", "tab-robot-track", "tab-calibration", "trail-canvas", "battery",
                    "lap-target-input", "lap-last", "lap-n"):
        expect(_by_id(page, test_id)).to_be_hidden()
    expect(page.locator('[data-role="no-sim-truth"]')).to_be_visible()

    expect(_by_id(page, "line-position")).to_have_text("7342 ‰ sensor")
    expect(_by_id(page, "error")).to_have_text("−158 ‰ sensor")
    expect(_by_id(page, "pid-p")).to_have_text("−7.1")
    expect(_by_id(page, "pwm-left")).to_have_text("0 PWM")

    _by_id(page, "btn-start").click()
    page.wait_for_timeout(200)
    assert server.commands("start") == [{"cmd": "start"}]
    assert capture.console_errors == []
