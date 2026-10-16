"""Cada schema del contrato es válido, tiene el `$id` esperado y resuelve sus `$ref`."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pytest
from jsonschema import Draft202012Validator

from conftest import SCHEMAS_DIR, read_json
from velocista_sim.contract import load_schemas

ID_BASE = "https://velocista-sim.local/contract/v1/"
SCHEMA_FILES = sorted(SCHEMAS_DIR.rglob("*.schema.json"))


def _id(path: Path) -> str:
    return path.relative_to(SCHEMAS_DIR).as_posix()


def _walk(node: Any) -> Iterator[tuple[str, Any]]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


@pytest.mark.parametrize("path", SCHEMA_FILES, ids=_id)
def test_schema_is_valid(path: Path) -> None:
    schema = read_json(path)
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == ID_BASE + _id(path)


@pytest.mark.parametrize("path", SCHEMA_FILES, ids=_id)
def test_schema_refs_resolve(path: Path) -> None:
    schema = read_json(path)
    resolver = load_schemas().registry.resolver(base_uri=schema["$id"])
    for key, value in _walk(schema):
        if key == "$ref":
            resolver.lookup(value)


@pytest.mark.parametrize("path", SCHEMA_FILES, ids=_id)
def test_schema_does_not_close_objects(path: Path) -> None:
    for key, value in _walk(read_json(path)):
        assert not (key == "additionalProperties" and value is False), (
            "los schemas no restringen additionalProperties (FR-005)"
        )
