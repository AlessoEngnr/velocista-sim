"""Prueba de carga corta del panel a 100 Hz (SC-003, versión de 30 s; la de 5 min es manual,
quickstart paso 20).

Marcada `slow`: queda excluida de `uv run pytest` y de la CI (`addopts = "-m 'not slow'"`).
Se corre con `uv run pytest -m slow tests/browser/test_panel_load.py`.
"""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page, expect

from support.browser import Capture, assert_frames_valid

pytestmark = [pytest.mark.slow, pytest.mark.timeout(120)]

RUN_SECONDS = 30
CHECK_EVERY_S = 3


def _by_id(page: Page, test_id: str):
    return page.get_by_test_id(test_id)


def _int(page: Page, test_id: str) -> int:
    return int(_by_id(page, test_id).text_content())


def _commit(page: Page, test_id: str, text: str) -> None:
    field = _by_id(page, test_id)
    field.fill(text)
    field.press("Enter")


def test_panel_holds_100_hz_for_30_seconds(page: Page, capture: Capture, live_url: str) -> None:
    page.goto(live_url)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    expect(_by_id(page, "kp-input")).to_have_value("0.0450")
    _commit(page, "rate-input", "100")
    expect(_by_id(page, "rate-hz")).to_have_text("100 Hz")

    _by_id(page, "btn-start").click()
    expect(_by_id(page, "run-status")).to_have_attribute("data-state", "running")

    deadline = time.monotonic() + RUN_SECONDS
    last_seq = _int(page, "seq")
    while time.monotonic() < deadline:
        page.wait_for_timeout(CHECK_EVERY_S * 1000)
        seq = _int(page, "seq")
        assert seq > last_seq, f"el seq no avanzó en {CHECK_EVERY_S} s ({last_seq} → {seq})"
        last_seq = seq
        # Si el robot se sale de pista la corrida termina: se vuelve a iniciar para seguir midiendo.
        if _by_id(page, "run-status").get_attribute("data-state") == "idle":
            _by_id(page, "btn-start").click()

    assert _int(page, "seq-lost") == 0
    assert int(_by_id(page, "trail-canvas").get_attribute("data-points")) > 0

    # Un cambio de `kp` se confirma (aparece en el campo tras el `config`) en menos de 1 s.
    started = time.monotonic()
    _commit(page, "kp-input", "0.04")
    expect(_by_id(page, "kp-input")).to_have_value("0.0400", timeout=1000)
    assert time.monotonic() - started < 1.0

    summaries = _by_id(page, "summaries").locator("li").count()
    if _by_id(page, "run-status").get_attribute("data-state") == "idle":
        _by_id(page, "btn-start").click()
        expect(_by_id(page, "run-status")).to_have_attribute("data-state", "running")
    _by_id(page, "btn-stop").click()
    expect(_by_id(page, "run-status")).to_have_attribute("data-state", "idle")
    expect(_by_id(page, "summaries").locator("li")).to_have_count(summaries + 1)

    assert_frames_valid(capture.frames)
    assert capture.console_errors == []
