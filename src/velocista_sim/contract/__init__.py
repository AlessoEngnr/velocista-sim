"""Validador del contrato v1 de velocista-sim (ver contract/contract-v1.md)."""

from .result import ValidationResult, Violation
from .schemas import load_schemas
from .validate import (
    effective_profile,
    validate_command,
    validate_message,
    validate_profile,
    validate_track,
)

__all__ = [
    "ValidationResult",
    "Violation",
    "effective_profile",
    "load_schemas",
    "validate_command",
    "validate_message",
    "validate_profile",
    "validate_track",
]
