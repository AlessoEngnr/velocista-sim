"""Utilidades compartidas por los tests del contrato."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from velocista_sim.contract import (
    ValidationResult,
    validate_command,
    validate_message,
    validate_profile,
    validate_track,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "contract" / "examples"
SCHEMAS_DIR = REPO_ROOT / "contract" / "schemas"

MESSAGE_FOLDERS = {"hello", "config", "telemetry", "event", "catalog", "error"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_example(path: Path) -> dict[str, Any]:
    """Lee el envoltorio de un ejemplo y resuelve su `hello` (nombre, objeto o `None`)."""
    example = read_json(path)
    hello = example.get("hello")
    if isinstance(hello, str):
        hello = read_json(EXAMPLES_DIR / "valid" / "hello" / f"{hello}.json")["message"]
    example["hello"] = hello
    return example


def validator_for(path: Path) -> Callable[[Any, dict | None], ValidationResult]:
    """Elige la función de validación según la carpeta del ejemplo."""
    relative = path.relative_to(EXAMPLES_DIR)
    folder = relative.parts[1]
    if folder in MESSAGE_FOLDERS:
        return validate_message
    if folder == "commands":
        return lambda message, hello: validate_command(message)
    if folder == "robot-profile":
        return lambda message, hello: validate_profile(message)
    if folder == "track":
        return lambda message, hello: validate_track(message)
    raise ValueError(f"Carpeta de ejemplos desconocida: {relative}")
