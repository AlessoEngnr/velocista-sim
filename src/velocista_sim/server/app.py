"""Aplicación FastAPI: WebSocket `/ws` con una sesión independiente por conexión (FR-001, FR-026)
y `GET /health` para el healthcheck de Railway (FR-042, contracts/http-health.md)."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Awaitable, Callable

import anyio
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect

from .catalog import load_catalog
from .pacer import OutboundQueue, Pacer
from .session import Session
from .settings import Settings

log = logging.getLogger(__name__)

CLOSE_POLICY_VIOLATION = 1008
CLOSE_TRY_AGAIN_LATER = 1013


def create_app(settings: Settings | None = None, clock: Callable[[], float] | None = None) -> FastAPI:
    """Crea la aplicación; carga y valida el catálogo (falla si es inválido).

    `clock` (segundos, monótono) es inyectable para los tests; por defecto `time.monotonic`.
    """
    settings = settings or Settings.from_env(os.environ)
    catalog = load_catalog(settings.config_dir, settings)
    clock = clock or time.monotonic
    app = FastAPI(title="velocista-sim")
    app.state.settings = settings
    app.state.catalog = catalog
    app.state.sessions = 0

    @app.get("/health")
    async def health() -> JSONResponse:
        sessions = app.state.sessions
        full = sessions >= settings.max_sessions
        body = {"status": "full" if full else "ok", "sessions": sessions, "max_sessions": settings.max_sessions}
        return JSONResponse(body, status_code=503 if full else 200)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        if app.state.sessions >= settings.max_sessions:
            log.warning("sesiones al máximo (%d): se rechaza una conexión con 1013", settings.max_sessions)
            await websocket.close(code=CLOSE_TRY_AGAIN_LATER)
            return
        app.state.sessions += 1
        try:
            session = Session(
                catalog, settings,
                robot_id=websocket.query_params.get("robot"),
                track_id=websocket.query_params.get("track"),
            )
            queue = OutboundQueue()
            for message in session.open():
                queue.put(message)
            pacer = Pacer(session, clock, queue)
            log.info("sesión %s abierta", session.session_id)
            try:
                await _serve(websocket, session, pacer, queue)
            finally:
                log.info("sesión %s cerrada", session.session_id)
        finally:
            app.state.sessions -= 1

    return app


async def _serve(websocket: WebSocket, session: Session, pacer: Pacer, queue: OutboundQueue) -> None:
    """Corre el ritmo, el envío y la lectura hasta que uno termine; luego cancela el resto."""
    async with anyio.create_task_group() as group:

        async def until_done(work: Callable[[], Awaitable[None]]) -> None:
            await work()
            group.cancel_scope.cancel()

        group.start_soon(until_done, pacer.run)
        group.start_soon(until_done, lambda: _send(websocket, queue))
        group.start_soon(until_done, lambda: _receive(websocket, session))

    if pacer.should_close:
        log.warning("sesión %s: el cliente no lee; se cierra con 1008", session.session_id)
        try:
            await websocket.close(code=CLOSE_POLICY_VIOLATION)
        except RuntimeError:
            pass


async def _send(websocket: WebSocket, queue: OutboundQueue) -> None:
    try:
        while True:
            message = await queue.get()
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
    except (WebSocketDisconnect, RuntimeError):
        return


async def _receive(websocket: WebSocket, session: Session) -> None:
    try:
        while True:
            frame = await websocket.receive()
            if frame["type"] == "websocket.disconnect":
                return
            text = frame.get("text")
            if text is None:
                text = (frame.get("bytes") or b"").decode("utf-8", errors="replace")
            session.submit(text)
    except (WebSocketDisconnect, RuntimeError):
        return
