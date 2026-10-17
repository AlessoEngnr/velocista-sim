"""Parseo de frames y mapeo de violaciones a códigos de error (contracts/ws-session.md)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from velocista_sim.contract import validate_message
from velocista_sim.server.commands import Command, CommandError, error_message, parse

REPO_ROOT = Path(__file__).resolve().parents[2]
INVALID_COMMANDS = REPO_ROOT / "contract" / "examples" / "invalid" / "commands"
VALID_COMMANDS = REPO_ROOT / "contract" / "examples" / "valid" / "commands"
OVAL_SMALL = VALID_COMMANDS / "load_track" / "oval-small.json"

SPANISH_HINTS = ("debe", "falta", "no ", "comando", "versión", "tipo", "valor", "JSON", "pista", "campo")


def _example(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["message"]


def _error(frame: str) -> CommandError:
    result = parse(frame)
    assert isinstance(result, CommandError), f"se esperaba un error para {frame[:80]!r}"
    assert result.message and any(hint in result.message for hint in SPANISH_HINTS), result.message
    return result


@pytest.mark.parametrize("frame", ["no es json", "{", "[1, 2]", '"start"', "3", "null"])
def test_invalid_json(frame: str) -> None:
    error = _error(frame)
    assert error.code == "invalid_json"
    assert error.cmd is None


@pytest.mark.parametrize("frame", ['{"cmd": "set_config", "params": {"kp": NaN}}',
                                   '{"cmd": "set_config", "params": {"kp": Infinity}}',
                                   '{"cmd": "set_config", "params": {"kp": -Infinity}}',
                                   '{"cmd": "set_config", "params": {"kp": 1e999}}'])
def test_non_finite_numbers_are_invalid_json(frame: str) -> None:
    assert _error(frame).code == "invalid_json"


@pytest.mark.parametrize("frame, cmd", [('{"cmd": "start", "v": 2}', "start"),
                                        ('{"cmd": "list", "v": "1"}', "list"),
                                        ('{"cmd": "stop", "v": true}', "stop"),
                                        ('{"cmd": 5, "v": 2}', None),
                                        ('{"cmd": "volar", "v": 2}', "volar")])
def test_unsupported_version(frame: str, cmd: str | None) -> None:
    error = _error(frame)
    assert error.code == "unsupported_version"
    assert error.cmd == cmd


@pytest.mark.parametrize("frame, cmd", [('{"v": 1}', None), ('{"cmd": 3}', None), ('{"cmd": "go"}', "go"),
                                        ('{"cmd": ""}', "")])
def test_unknown_cmd(frame: str, cmd: str | None) -> None:
    error = _error(frame)
    assert error.code == "unknown_cmd"
    if cmd:
        assert error.cmd == cmd
    else:
        assert error.cmd is None


@pytest.mark.parametrize("command", [
    {"cmd": "set_config"},
    {"cmd": "set_config", "base_speed": 180.5},
    {"cmd": "set_config", "params": {}},
    {"cmd": "set_config", "controller": "pd"},
    {"cmd": "set_rate"},
    {"cmd": "set_rate", "hz": 20.5},
    {"cmd": "load"},
    {"cmd": "load", "robot_id": 1},
    {"cmd": "load_track"},
    {"cmd": "load_track", "track": "oval-01"},
    {"cmd": "set_profile"},
    {"cmd": "set_profile", "measured": {}},
    {"cmd": "set_profile", "measured": {"line_sensors": 8}},
    {"cmd": "set_profile", "measured": {"wheelbase": 0.128}},
    {"cmd": "set_profile", "measured": {"encoder_ticks_per_rev": 12.5}},
])
def test_invalid_params(command: dict) -> None:
    error = _error(json.dumps(command))
    assert error.code == "invalid_params"
    assert error.cmd == command["cmd"]


@pytest.mark.parametrize("command", [
    {"cmd": "set_rate", "hz": 150},
    {"cmd": "set_rate", "hz": 5},
    {"cmd": "set_config", "base_speed": 300},
    {"cmd": "set_config", "params": {"kp": -1}},
    {"cmd": "set_profile", "measured": {"wheelbase_m": -0.1}},
])
def test_out_of_range(command: dict) -> None:
    error = _error(json.dumps(command))
    assert error.code == "out_of_range"
    assert error.cmd == command["cmd"]


def test_mixed_violations_prefer_invalid_params() -> None:
    error = _error(json.dumps({"cmd": "set_config", "base_speed": 300, "params": {"kp": "alto"}}))
    assert error.code == "invalid_params"


@pytest.mark.parametrize("name", ["invalid-track.json", "track-gaps-overlap.json"])
def test_invalid_track(name: str) -> None:
    command = _example(INVALID_COMMANDS / "load_track" / name)
    error = _error(json.dumps(command))
    assert error.code == "invalid_track"
    assert error.cmd == "load_track"


def test_invalid_examples_never_parse() -> None:
    for path in sorted(INVALID_COMMANDS.rglob("*.json")):
        result = parse(json.dumps(_example(path)))
        assert isinstance(result, CommandError), path


def test_valid_examples_parse() -> None:
    for path in sorted(VALID_COMMANDS.rglob("*.json")):
        command = _example(path)
        result = parse(json.dumps(command))
        assert isinstance(result, Command), (path, result)
        assert result.cmd == command["cmd"]
        assert result.fields == command


def test_load_track_oval_small_parses() -> None:
    result = parse(json.dumps(_example(OVAL_SMALL)))
    assert isinstance(result, Command)
    assert result.fields["track"]["id"] == "oval-small"


def test_error_message_follows_contract() -> None:
    error = _error('{"cmd": "set_rate", "hz": 150}')
    message = error_message(error, 42)
    assert message["type"] == "error" and message["t_ms"] == 42 and message["cmd"] == "set_rate"
    assert validate_message(message).ok

    without_cmd = error_message(_error("{"), 0)
    assert "cmd" not in without_cmd
    assert validate_message(without_cmd).ok


def test_error_message_omits_empty_cmd() -> None:
    message = error_message(_error('{"cmd": ""}'), 0)
    assert "cmd" not in message
    assert validate_message(message).ok
