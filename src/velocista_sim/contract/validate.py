"""Validación de mensajes, comandos, perfiles y pistas contra el contrato v1.

Capa 1: JSON Schema. Capa 2: reglas que dependen del `hello` de la sesión. Capa 3: semántica
de la pista. Ver specs/001-contrato-v1/data-model.md § Reglas de validación.
"""

from __future__ import annotations

import functools
import json
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from .context_rules import context_violations
from .result import ValidationResult, Violation, sorted_violations
from .schemas import SchemaStore, load_schemas


def validate_message(message: Any, hello: dict | None = None) -> ValidationResult:
    """Valida un mensaje servidor→cliente.

    Elige el schema por `type`. Con `hello` (el último de la sesión) aplica además las reglas
    contextuales; si el mensaje es un `hello`, se usa a sí mismo como contexto.
    """
    if not isinstance(message, dict):
        return _not_an_object()
    if message.get("type") == "hello":
        hello = message
    context_checked = hello is not None

    name = _schema_name("messages", message.get("type"))
    if name is None:
        violation = Violation(
            "unknown_type", "/type", f"tipo de mensaje desconocido o ausente: {_show(message.get('type'))}"
        )
        return ValidationResult((violation,), context_checked)

    violations = _schema_violations(name, message)
    if not violations and hello is not None:
        violations = _context_violations(message, hello)
    return ValidationResult(sorted_violations(violations), context_checked)


def validate_command(command: Any) -> ValidationResult:
    """Valida un comando cliente→servidor; elige el schema por `cmd`."""
    if not isinstance(command, dict):
        return _not_an_object()
    name = _schema_name("commands", command.get("cmd"))
    if name is None:
        violation = Violation(
            "unknown_cmd", "/cmd", f"comando desconocido o ausente: {_show(command.get('cmd'))}"
        )
        return ValidationResult((violation,), False)
    return ValidationResult(sorted_violations(_schema_violations(name, command)), False)


def validate_profile(profile: Any) -> ValidationResult:
    """Valida un perfil del robot."""
    if not isinstance(profile, dict):
        return _not_an_object()
    return ValidationResult(sorted_violations(_schema_violations("robot-profile", profile)), False)


def validate_track(track: Any) -> ValidationResult:
    """Valida una pista track v1: schema y semántica de pista."""
    if not isinstance(track, dict):
        return _not_an_object()
    violations = _schema_violations("track", track)
    if not violations:
        violations = _track_violations(track)
    return ValidationResult(sorted_violations(violations), False)


# --- Capas 2 y 3 -------------------------------------------------------------------------


def _context_violations(message: dict, hello: dict) -> list[Violation]:
    """Capa 2: reglas que dependen del `hello` de la sesión."""
    return context_violations(message, hello)


def _track_violations(track: dict) -> list[Violation]:
    """Capa 3: semántica de la pista."""
    return []


# --- Capa 1: JSON Schema ------------------------------------------------------------------


def _schema_name(folder: str, discriminator: Any) -> str | None:
    if not isinstance(discriminator, str):
        return None
    name = f"{folder}/{discriminator}"
    return name if name in load_schemas() else None


def _schema_violations(name: str, instance: dict) -> list[Violation]:
    validator = _validator(load_schemas(), name)
    violations: list[Violation] = []
    for error in validator.iter_errors(instance):
        violations.extend(_to_violations(error))
    return violations


@functools.cache
def _validator(store: SchemaStore, name: str) -> Draft202012Validator:
    return Draft202012Validator(
        store.get(name),
        registry=store.registry,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def _to_violations(error: ValidationError) -> list[Violation]:
    path = list(error.absolute_path)
    if error.validator == "required":
        instance = error.instance if isinstance(error.instance, dict) else {}
        missing = [prop for prop in error.validator_value if prop not in instance]
        return [
            Violation("required", _pointer([*path, prop]), f"falta el campo obligatorio «{prop}»")
            for prop in missing
        ]
    return [Violation(str(error.validator), _pointer(path), _describe(error))]


def _describe(error: ValidationError) -> str:
    keyword, value, instance = error.validator, error.validator_value, error.instance
    shown = _show(instance)
    match keyword:
        case "type":
            expected = " o ".join(value) if isinstance(value, list) else value
            return f"tipo incorrecto: {shown} no es de tipo {expected}"
        case "minimum":
            return f"el valor {shown} es menor que el mínimo {_show(value)}"
        case "maximum":
            return f"el valor {shown} es mayor que el máximo {_show(value)}"
        case "exclusiveMinimum":
            return f"el valor {shown} debe ser mayor que {_show(value)}"
        case "exclusiveMaximum":
            return f"el valor {shown} debe ser menor que {_show(value)}"
        case "enum":
            return f"el valor {shown} no es uno de {_show(value)}"
        case "const":
            return f"el valor {shown} debe ser {_show(value)}"
        case "minItems":
            return f"la lista debe tener al menos {value} elementos"
        case "maxItems":
            return f"la lista debe tener como máximo {value} elementos"
        case "minLength":
            return f"el texto debe tener al menos {value} caracteres"
        case "uniqueItems":
            return "la lista no admite elementos repetidos"
        case "minProperties":
            return f"el objeto debe tener al menos {value} campos"
        case "not":
            return "el mensaje contiene campos que no corresponden en este caso"
        case "anyOf":
            return "el mensaje no cumple ninguna de las alternativas permitidas"
        case _:
            return f"no cumple la regla «{keyword}» del schema"


def _pointer(parts: list[Any]) -> str:
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def _show(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _not_an_object() -> ValidationResult:
    violation = Violation("type", "", "el mensaje debe ser un objeto JSON")
    return ValidationResult((violation,), False)
