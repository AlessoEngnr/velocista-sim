"""Tipos de resultado del validador del contrato."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    """Una regla del contrato que el mensaje no cumple.

    `rule` es la palabra clave de JSON Schema que falla (`required`, `maximum`, …) o el
    identificador de una regla propia de data-model.md; `path` es un JSON Pointer dentro del
    mensaje (`""` es la raíz); `message` explica el fallo en español.
    """

    rule: str
    path: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    """Resultado de validar un mensaje, comando, perfil o pista."""

    violations: tuple[Violation, ...]
    context_checked: bool

    @property
    def ok(self) -> bool:
        """`True` si no hay violaciones."""
        return not self.violations


def sorted_violations(violations: list[Violation]) -> tuple[Violation, ...]:
    """Quita duplicados (`rule`, `path`) y ordena por `path` y luego por `rule`."""
    unique: dict[tuple[str, str], Violation] = {}
    for violation in violations:
        unique.setdefault((violation.rule, violation.path), violation)
    return tuple(sorted(unique.values(), key=lambda v: (v.path, v.rule)))
