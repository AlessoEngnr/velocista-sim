"""Validación de cada mensaje que emite el simulador (principio VII, research R10).

`MessageChecker` valida mensajes sueltos (núcleo `Session` sin E/S); `ContractClient` envuelve
una conexión WebSocket de `fastapi.testclient.TestClient` y valida cada mensaje recibido.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from velocista_sim.contract import validate_message


class MessageChecker:
    """Comprueba el contrato y las reglas de secuencia de una sesión, mensaje a mensaje.

    Cualquier violación levanta `AssertionError` con la explicación.
    """

    def __init__(self, allow_drops: bool = False) -> None:
        self.allow_drops = allow_drops
        self.hello: dict | None = None
        self.messages: list[dict] = []
        self.types: set[str] = set()
        self.events: set[str] = set()
        self.codes: set[str] = set()
        self._last_t_ms: int | None = None
        self._last_seq: int | None = None
        self._finished_runs: set[str] = set()
        self._pending_off_track: str | None = None

    def check(self, message: Any) -> dict:
        """Valida `message` y lo registra; devuelve el mismo mensaje."""
        assert isinstance(message, dict), f"el mensaje no es un objeto: {message!r}"
        index = len(self.messages)
        kind = message.get("type")

        if index == 0:
            assert kind == "hello", f"el primer mensaje debe ser hello, llegó {kind!r}"
        elif index == 1:
            assert kind == "config", f"el segundo mensaje debe ser config, llegó {kind!r}"

        if kind == "hello":
            self.hello = message
        result = validate_message(message, self.hello)
        assert result.ok, f"mensaje fuera de contrato: {message!r}\n" + "\n".join(
            f"  {v.rule} {v.path}: {v.message}" for v in result.violations
        )
        _assert_no_centerline(message)

        t_ms = message["t_ms"]
        if self._last_t_ms is not None:
            assert t_ms >= self._last_t_ms, f"t_ms decrece: {self._last_t_ms} → {t_ms}"
        self._last_t_ms = t_ms

        if self._pending_off_track is not None:
            assert (
                kind == "event"
                and message.get("event") == "run_finished"
                and message.get("run_id") == self._pending_off_track
            ), f"off_track de {self._pending_off_track} no va seguido de run_finished: {message!r}"
            self._pending_off_track = None

        if kind == "telemetry":
            self._check_seq(message["seq"])
        elif kind == "event":
            self._check_event(message)
        elif kind == "error":
            self.codes.add(message["code"])

        self.types.add(kind)
        self.messages.append(message)
        return message

    def check_all(self, messages: list[dict]) -> list[dict]:
        """Valida una lista de mensajes en orden."""
        for message in messages:
            self.check(message)
        return messages

    def _check_seq(self, seq: int) -> None:
        if self._last_seq is None:
            assert seq == 0, f"el primer seq de telemetry debe ser 0, llegó {seq}"
        elif self.allow_drops:
            assert seq > self._last_seq, f"seq no crece: {self._last_seq} → {seq}"
        else:
            assert seq == self._last_seq + 1, f"seq salta: {self._last_seq} → {seq}"
        self._last_seq = seq

    def _check_event(self, message: dict) -> None:
        event = message["event"]
        self.events.add(event)
        if event == "run_finished":
            run_id = message["run_id"]
            assert run_id not in self._finished_runs, f"más de un run_finished para {run_id}"
            self._finished_runs.add(run_id)
        elif event == "off_track":
            self._pending_off_track = message["run_id"]


def _assert_no_centerline(value: Any, path: str = "") -> None:
    """Ningún mensaje lleva la geometría de la pista (FR-008)."""
    if isinstance(value, dict):
        for key, item in value.items():
            assert key != "centerline", f"el mensaje contiene centerline en {path}/{key}"
            _assert_no_centerline(item, f"{path}/{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_centerline(item, f"{path}/{index}")


class ContractClient:
    """Envoltorio de una conexión WebSocket de `TestClient` que valida cada mensaje recibido."""

    def __init__(self, websocket: Any, allow_drops: bool = False) -> None:
        self.websocket = websocket
        self.checker = MessageChecker(allow_drops=allow_drops)

    @property
    def messages(self) -> list[dict]:
        return self.checker.messages

    def receive_json(self) -> dict:
        """Recibe un mensaje y lo valida."""
        return self.checker.check(json.loads(self.websocket.receive_text()))

    def send_cmd(self, cmd: str, **fields: Any) -> None:
        """Envía el comando `cmd` con `v = 1` y los campos dados."""
        self.websocket.send_text(json.dumps({"cmd": cmd, "v": 1, **fields}))

    def send_text(self, frame: str) -> None:
        """Envía un frame crudo (para probar frames inválidos)."""
        self.websocket.send_text(frame)

    def wait_for(self, predicate: Callable[[dict], bool], max_msgs: int = 5000) -> dict:
        """Recibe hasta encontrar un mensaje que cumpla `predicate` y lo devuelve."""
        for _ in range(max_msgs):
            message = self.receive_json()
            if predicate(message):
                return message
        raise AssertionError(f"no llegó el mensaje esperado en {max_msgs} mensajes")


def is_event(name: str) -> Callable[[dict], bool]:
    """Predicado: evento `name`."""
    return lambda m: m.get("type") == "event" and m.get("event") == name


def is_type(kind: str) -> Callable[[dict], bool]:
    """Predicado: mensaje de tipo `kind`."""
    return lambda m: m.get("type") == kind


def is_error(code: str) -> Callable[[dict], bool]:
    """Predicado: error con código `code`."""
    return lambda m: m.get("type") == "error" and m.get("code") == code
