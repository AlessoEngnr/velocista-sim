"""Pruebas de navegador del panel con Playwright (research R12).

Todo test de este directorio lleva el marcador `browser`. Si Chromium no está instalado se
omiten con el comando de instalación como motivo; con `VELOCISTA_REQUIRE_BROWSER=1` (CI) la falta
del navegador es un fallo. Cada página registra los errores de consola y los frames WebSocket
enviados y recibidos en `capture`, que los tests validan con `support.browser.assert_frames_valid`
(principio VII).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest
from playwright.sync_api import Browser, Error, Page, WebSocket, sync_playwright

from support.browser import Capture, Frame, text_payload
from support.live_server import start_live_server

BROWSER_DIR = Path(__file__).resolve().parent
INSTALL_HINT = "Falta Chromium: uv run playwright install chromium"
VIEWPORT = {"width": 1440, "height": 900}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if BROWSER_DIR in item.path.parents:
            item.add_marker(pytest.mark.browser)


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch(headless=True)
        except Error as exc:
            if "Executable doesn't exist" not in str(exc):
                raise
            if os.environ.get("VELOCISTA_REQUIRE_BROWSER") == "1":
                pytest.fail(INSTALL_HINT)
            pytest.skip(INSTALL_HINT)
        yield launched
        launched.close()


@pytest.fixture(scope="session")
def live_url() -> Iterator[str]:
    """URL `http://127.0.0.1:<puerto>` de un uvicorn real con el catálogo de `config/`."""
    with start_live_server() as url:
        yield url


@pytest.fixture
def capture() -> Capture:
    return Capture()


@pytest.fixture
def page(browser: Browser, capture: Capture) -> Iterator[Page]:
    context = browser.new_context(viewport=VIEWPORT)
    new_page = context.new_page()

    def on_console(message) -> None:
        if message.type == "error":
            capture.console_errors.append(message.text)

    def on_websocket(socket: WebSocket) -> None:
        index = len(capture.sockets)
        capture.sockets.append(socket.url)
        socket.on("framesent", lambda payload: capture.frames.append(Frame(index, "sent", text_payload(payload))))
        socket.on(
            "framereceived", lambda payload: capture.frames.append(Frame(index, "received", text_payload(payload)))
        )

    new_page.on("console", on_console)
    new_page.on("pageerror", lambda exc: capture.console_errors.append(str(exc)))
    new_page.on("websocket", on_websocket)
    yield new_page
    context.close()
