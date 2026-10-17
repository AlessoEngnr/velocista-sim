"""Parseo de frames de comandos y mapeo de violaciones a códigos de error (research R8).

Precedencia (contracts/ws-session.md): `invalid_json` → `unsupported_version` →
`unknown_cmd` → violaciones del schema (`invalid_track`, `invalid_params`, `out_of_range`).
Las reglas de estado (`run_active`, `no_run`, `unknown_robot`) las aplica la sesión.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

from velocista_sim.contract import Violation, load_schemas, validate_command

RANGE_RULES = frozenset({"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"})


@dataclass(frozen=True)
class Command:
    """Comando válido según el contrato; `fields` es el objeto JSON completo."""

    cmd: str
    fields: dict[str, Any]


@dataclass(frozen=True)
class CommandError:
    """Rechazo de un frame: `code` del contrato, `cmd` si era un string no vacío, `message` en español."""

    code: str
    cmd: str | None
    message: str


class _NonFinite(ValueError):
    pass


def _reject_constant(name: str) -> float:
    raise _NonFinite(f"el número {name} no está permitido en JSON")


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise _NonFinite(f"el número {text} no es finito")
    return value


def parse(frame: str) -> Command | CommandError:
    """Interpreta un frame de texto recibido por el WebSocket."""
    try:
        data = json.loads(frame, parse_constant=_reject_constant, parse_float=_finite_float)
    except _NonFinite as exc:
        return CommandError("invalid_json", None, f"el frame no es JSON válido: {exc}")
    except (ValueError, RecursionError):
        return CommandError("invalid_json", None, "el frame no es JSON válido")
    if not isinstance(data, dict):
        return CommandError("invalid_json", None, "el frame debe ser un objeto JSON")

    raw_cmd = data.get("cmd")
    cmd = raw_cmd if isinstance(raw_cmd, str) and raw_cmd else None

    if "v" in data and not _is_version_one(data["v"]):
        return CommandError(
            "unsupported_version", cmd,
            f"versión de protocolo no soportada: {json.dumps(data['v'], ensure_ascii=False)}; se espera 1",
        )

    if not isinstance(raw_cmd, str) or f"commands/{raw_cmd}" not in load_schemas():
        shown = json.dumps(raw_cmd, ensure_ascii=False) if "cmd" in data else "ausente"
        return CommandError("unknown_cmd", cmd, f"comando desconocido: {shown}")

    result = validate_command(data)
    if result.ok:
        return Command(raw_cmd, data)
    code, violation = _classify(raw_cmd, data, result.violations)
    where = f" (en «{violation.path}»)" if violation.path else ""
    prefix = "pista inválida: " if code == "invalid_track" else ""
    return CommandError(code, cmd, f"{raw_cmd}: {prefix}{violation.message}{where}")


def _is_version_one(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == 1


def _classify(cmd: str, data: dict, violations: tuple[Violation, ...]) -> tuple[str, Violation]:
    """Código de error y violación que lo explica, según los grupos de research R8."""
    if cmd == "load_track" and isinstance(data.get("track"), dict):
        track = [v for v in violations if v.path.startswith("/track/") or v.path == "/track"]
        if track:
            return "invalid_track", track[0]
    params = [v for v in violations if v.rule not in RANGE_RULES]
    if params:
        return "invalid_params", params[0]
    return "out_of_range", violations[0]


def error_message(error: CommandError, t_ms: int) -> dict[str, Any]:
    """Mensaje `error` del contrato para un rechazo."""
    message: dict[str, Any] = {"type": "error", "v": 1, "t_ms": t_ms, "code": error.code}
    if error.cmd:
        message["cmd"] = error.cmd
    message["message"] = error.message
    return message
