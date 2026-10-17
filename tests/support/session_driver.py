"""Conductor del núcleo `Session` sin E/S para los tests: cada mensaje pasa por `MessageChecker`."""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any, Callable

from velocista_sim.server.catalog import Catalog, load_catalog
from velocista_sim.server.session import Session
from velocista_sim.server.settings import Settings

from .contract_client import MessageChecker

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
OVAL_SMALL = REPO_ROOT / "contract" / "examples" / "valid" / "commands" / "load_track" / "oval-small.json"


@functools.cache
def default_catalog() -> Catalog:
    return load_catalog(CONFIG_DIR, Settings(config_dir=CONFIG_DIR))


def oval_small_track() -> dict:
    return json.loads(OVAL_SMALL.read_text(encoding="utf-8"))["message"]["track"]


class SessionDriver:
    """Abre una sesión, envía comandos y avanza pasos validando todo lo emitido."""

    def __init__(self, seed: int = 1, robot_id: str | None = None, track_id: str | None = None) -> None:
        settings = Settings(seed=seed, config_dir=CONFIG_DIR)
        self.session = Session(default_catalog(), settings, robot_id=robot_id, track_id=track_id)
        self.checker = MessageChecker()
        self.opening = self.checker.check_all(self.session.open())

    @property
    def messages(self) -> list[dict]:
        return self.checker.messages

    def send(self, cmd: str, **fields: Any) -> None:
        self.session.submit(json.dumps({"cmd": cmd, "v": 1, **fields}))

    def send_raw(self, frame: str) -> None:
        self.session.submit(frame)

    def run(self, steps: int) -> list[dict]:
        """Avanza `steps` pasos y devuelve los mensajes emitidos."""
        emitted: list[dict] = []
        for _ in range(steps):
            emitted += self.checker.check_all(self.session.step())
        return emitted

    def run_until(self, predicate: Callable[[dict], bool], max_steps: int) -> tuple[dict, list[dict]]:
        """Avanza hasta que se emita un mensaje que cumpla `predicate`."""
        emitted: list[dict] = []
        for _ in range(max_steps):
            for message in self.checker.check_all(self.session.step()):
                emitted.append(message)
                if predicate(message):
                    return message, emitted
        raise AssertionError(f"no se emitió el mensaje esperado en {max_steps} pasos")

    def command(self, cmd: str, **fields: Any) -> list[dict]:
        """Envía un comando y avanza un paso: devuelve lo emitido en ese paso."""
        self.send(cmd, **fields)
        return self.run(1)


def of_type(messages: list[dict], kind: str) -> list[dict]:
    return [m for m in messages if m["type"] == kind]


def events(messages: list[dict], name: str | None = None) -> list[dict]:
    return [m for m in messages if m["type"] == "event" and (name is None or m["event"] == name)]
