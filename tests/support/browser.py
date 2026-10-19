"""Captura de frames WebSocket de las pruebas de navegador y su validación contra el contrato
(specs/003-panel-laboratorio, research R12, principio VII)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from velocista_sim.contract import validate_command, validate_message


@dataclass(frozen=True)
class Frame:
    """Un frame WebSocket de la página: `socket` numera las conexiones en orden de apertura."""

    socket: int
    direction: str  # "sent" | "received"
    payload: str


@dataclass
class Capture:
    """Lo que la página hizo durante el test."""

    console_errors: list[str] = field(default_factory=list)
    frames: list[Frame] = field(default_factory=list)
    sockets: list[str] = field(default_factory=list)

    def sent(self) -> list[dict]:
        return [json.loads(f.payload) for f in self.frames if f.direction == "sent"]

    def received(self) -> list[dict]:
        return [json.loads(f.payload) for f in self.frames if f.direction == "received"]


def text_payload(payload: str | bytes) -> str:
    return payload if isinstance(payload, str) else payload.decode("utf-8")


def assert_frames_valid(frames: list[Frame]) -> None:
    """Valida cada comando enviado con `validate_command` y cada mensaje recibido con
    `validate_message` y el último `hello` de su conexión."""
    problems: list[str] = []
    hellos: dict[int, dict] = {}
    for frame in frames:
        try:
            data = json.loads(frame.payload)
        except json.JSONDecodeError:
            problems.append(f"frame {frame.direction} no es JSON: {frame.payload[:80]}")
            continue
        if frame.direction == "sent":
            result = validate_command(data)
        else:
            if isinstance(data, dict) and data.get("type") == "hello":
                hellos[frame.socket] = data
            result = validate_message(data, hellos.get(frame.socket))
        if not result.ok:
            problems.append(f"frame {frame.direction} inválido {frame.payload[:120]}: {result.violations}")
    assert not problems, "\n".join(problems)
