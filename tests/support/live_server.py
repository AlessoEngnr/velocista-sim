"""Servidor `uvicorn` real en un hilo y puerto libre, compartido por los tests de integración y de
navegador (specs/003-panel-laboratorio, research R12)."""

from __future__ import annotations

import contextlib
import socket
import threading
import time
from typing import Iterator

import uvicorn

from velocista_sim.server.app import create_app
from velocista_sim.server.settings import Settings

from .session_driver import CONFIG_DIR


def free_port() -> int:
    """Un puerto TCP libre en `127.0.0.1`."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextlib.contextmanager
def start_live_server(settings: Settings | None = None) -> Iterator[str]:
    """Arranca la aplicación en un hilo y devuelve `http://127.0.0.1:<puerto>`; la detiene al salir."""
    port = free_port()
    app = create_app(settings or Settings(config_dir=CONFIG_DIR))
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning", timeout_graceful_shutdown=1
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "uvicorn no arrancó"
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
