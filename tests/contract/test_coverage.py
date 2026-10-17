"""Cobertura mínima de ejemplos del contrato (SC-001, SC-003, SC-005 y FR-002)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterator

import pytest

from conftest import EXAMPLES_DIR, REPO_ROOT, SCHEMAS_DIR, read_json

DATA_MODEL = REPO_ROOT / "specs" / "001-contrato-v1" / "data-model.md"
SCHEMA_SUFFIX = ".schema.json"

# Schemas sin campos propios además del discriminador: exentos de la regla G1.
WITHOUT_OWN_FIELDS = {"commands/start", "commands/stop", "commands/list", "commands/reset"}
BOUND_RULES = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}

# Mensajes, subtipos de evento y comandos que el PDF v1.1 ejemplifica de forma completa.
# load_track, la pista y el perfil completo quedan fuera: el PDF los muestra abreviados.
PDF_FOLDERS = [
    "hello", "config", "telemetry", "event", "catalog", "error",
    "commands/start", "commands/stop", "commands/set_config", "commands/set_rate",
    "commands/list", "commands/reset", "commands/load", "commands/set_profile",
]
EVENT_SUBTYPES = ["run_started", "lap", "off_track", "run_finished"]


def _schema_names() -> list[str]:
    names = [
        path.relative_to(SCHEMAS_DIR).as_posix().removesuffix(SCHEMA_SUFFIX)
        for path in SCHEMAS_DIR.rglob(f"*{SCHEMA_SUFFIX}")
    ]
    return sorted(name for name in names if name != "common")


def _example_folder(schema_name: str) -> str:
    """`messages/telemetry` → `telemetry`; `commands/start` y `track` quedan igual."""
    return schema_name.removeprefix("messages/")


def _examples(kind: str, folder: str) -> list[dict]:
    return [read_json(path) for path in sorted((EXAMPLES_DIR / kind / folder).glob("*.json"))]


def _expected_rules(folder: str) -> set[str]:
    return {e["rule"] for example in _examples("invalid", folder) for e in example["expected"]}


def _walk(node: Any) -> Iterator[tuple[str, Any]]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _own_rule_ids() -> list[str]:
    """Identificadores de las reglas de las capas 2 y 3, leídos de data-model.md."""
    text = DATA_MODEL.read_text(encoding="utf-8")
    rules: list[str] = []
    for layer in ("Capa 2", "Capa 3"):
        section = text.split(f"### {layer}", 1)[1].split("\n### ", 1)[0]
        rules += re.findall(r"^\| `([a-z_]+)` \|", section, flags=re.MULTILINE)
    return rules


SCHEMA_NAMES = _schema_names()
OWN_RULES = _own_rule_ids()


def test_all_schemas_are_listed() -> None:
    # 6 mensajes + 9 comandos + perfil + pista.
    assert len(SCHEMA_NAMES) == 17, SCHEMA_NAMES


@pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
def test_every_schema_has_valid_and_invalid_examples(schema_name: str) -> None:
    folder = _example_folder(schema_name)
    assert _examples("valid", folder), f"falta un ejemplo válido en valid/{folder}/"
    assert _examples("invalid", folder), f"falta un ejemplo inválido en invalid/{folder}/"


@pytest.mark.parametrize("subtype", EVENT_SUBTYPES)
def test_every_event_subtype_has_a_valid_example(subtype: str) -> None:
    assert any(example["message"].get("event") == subtype for example in _examples("valid", "event"))


def test_own_rules_are_read_from_data_model() -> None:
    assert len(OWN_RULES) == 24, OWN_RULES
    assert len(set(OWN_RULES)) == len(OWN_RULES)


@pytest.mark.parametrize("rule", OWN_RULES)
def test_every_own_rule_has_an_invalid_example(rule: str) -> None:
    used = {
        e["rule"]
        for path in (EXAMPLES_DIR / "invalid").rglob("*.json")
        for e in read_json(path)["expected"]
    }
    assert rule in used, f"ningún ejemplo inválido ilustra la regla {rule}"


@pytest.mark.parametrize("folder", PDF_FOLDERS)
def test_pdf_examples_are_present(folder: str) -> None:
    assert any(
        example["description"].startswith("PDF v1.1:") for example in _examples("valid", folder)
    ), f"falta el ejemplo del PDF v1.1 en valid/{folder}/"


@pytest.mark.parametrize("subtype", EVENT_SUBTYPES)
def test_pdf_event_subtypes_are_present(subtype: str) -> None:
    assert any(
        example["description"].startswith("PDF v1.1:") and example["message"]["event"] == subtype
        for example in _examples("valid", "event")
    )


@pytest.mark.parametrize(
    "schema_name", [name for name in SCHEMA_NAMES if name not in WITHOUT_OWN_FIELDS]
)
def test_schema_rules_have_invalid_examples(schema_name: str) -> None:
    """G1: obligatorio ausente, tipo incorrecto y, si hay cotas numéricas, fuera de rango."""
    schema = read_json(SCHEMAS_DIR / f"{schema_name}{SCHEMA_SUFFIX}")
    rules = _expected_rules(_example_folder(schema_name))
    if schema.get("required"):
        assert "required" in rules, f"{schema_name}: falta un inválido con rule = required"
        assert "type" in rules, f"{schema_name}: falta un inválido con rule = type"
    if any(key in BOUND_RULES for key, _ in _walk(schema)):
        assert rules & BOUND_RULES, f"{schema_name}: falta un inválido fuera de rango"
