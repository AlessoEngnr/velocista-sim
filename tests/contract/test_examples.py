"""Cada ejemplo de contract/examples se valida según su carpeta (example-format.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import EXAMPLES_DIR, load_example, validator_for

VALID_FILES = sorted((EXAMPLES_DIR / "valid").rglob("*.json"))
INVALID_FILES = sorted((EXAMPLES_DIR / "invalid").rglob("*.json"))


def _id(path: Path) -> str:
    return path.relative_to(EXAMPLES_DIR).as_posix()


def _check_description(example: dict) -> None:
    description = example.get("description")
    assert isinstance(description, str) and description.strip(), "falta description"
    assert "message" in example, "falta message"


@pytest.mark.parametrize("path", VALID_FILES, ids=_id)
def test_valid_example(path: Path) -> None:
    example = load_example(path)
    _check_description(example)
    assert "expected" not in example, "los ejemplos válidos no llevan expected"

    result = validator_for(path)(example["message"], example["hello"])

    assert result.ok, [(v.rule, v.path, v.message) for v in result.violations]


@pytest.mark.parametrize("path", INVALID_FILES, ids=_id)
def test_invalid_example(path: Path) -> None:
    example = load_example(path)
    _check_description(example)
    expected = example.get("expected")
    assert isinstance(expected, list) and expected, "los ejemplos inválidos llevan expected no vacío"

    result = validator_for(path)(example["message"], example["hello"])

    actual = {(v.rule, v.path) for v in result.violations}
    assert actual == {(e["rule"], e["path"]) for e in expected}, [
        (v.rule, v.path, v.message) for v in result.violations
    ]
