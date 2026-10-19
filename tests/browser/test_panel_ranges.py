"""Los rangos que valida el panel son iguales o más estrictos que los del contrato, nunca más
permisivos (FR-037): la tabla `TUNING` de `views/control.js` contra `set_config`/`set_rate`, y
`PROFILE_PARAMS` de `profile-params.js` contra `set_profile` (con cada `adc_bits` posible).

Las tablas se leen del panel servido (módulos importados en la página) y los rangos del JSON
Schema del contrato, resolviendo los `$ref`; además se prueban los valores justo fuera de cada
borde con las funciones de validación del propio panel."""

from __future__ import annotations

import json
import math
from functools import cache
from pathlib import Path

import pytest
from playwright.sync_api import Page

from velocista_sim.contract import validate_command

SCHEMAS = Path(__file__).resolve().parents[2] / "contract" / "schemas"
COMMANDS = SCHEMAS / "commands"
ADC_BITS = range(8, 17)  # rango de `capabilities.adc_bits` en el contrato

PANEL_TABLES = """
async () => {
  const control = await import("/js/views/control.js");
  const profile = await import("/js/profile-params.js");
  const bits = [null, ...Array.from({ length: 9 }, (_, i) => i + 8)];
  return {
    tuning: control.TUNING.map((c) => ({ field: c.field, integer: c.integer, bounds: c.bounds })),
    profile: profile.PROFILE_PARAMS.map((p) => ({
      key: p.key,
      integer: p.integer,
      bounds: Object.fromEntries(bits.map((b) => [String(b), profile.paramBounds(p, b)])),
    })),
  };
}
"""

# Para cada texto, si el panel lo acepta: [[tabla, clave, adcBits, texto], ...] → [bool, ...].
PANEL_ACCEPTS = """
async (cases) => {
  const control = await import("/js/views/control.js");
  const profile = await import("/js/profile-params.js");
  return cases.map(([table, key, bits, text]) => {
    if (table === "tuning") {
      const item = control.TUNING.find((c) => c.field === key);
      return control.parseTuning(item, text) !== null;
    }
    const item = profile.PROFILE_PARAMS.find((p) => p.key === key);
    return profile.parseDraft(item, text, bits) !== null;
  });
}
"""


@cache
def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(node: dict, base: Path) -> tuple[dict, Path]:
    """Sigue los `$ref` (relativos a `base`) hasta un nodo sin referencia."""
    while "$ref" in node:
        file, _, pointer = node["$ref"].partition("#")
        base = (base.parent / file).resolve() if file else base
        node = _load(base)
        for part in filter(None, pointer.split("/")):
            node = node[part]
    return node, base


def _schema_at(schema_file: Path, *path: str) -> dict:
    node, base = _resolve(_load(schema_file), schema_file)
    for part in path:
        node, base = _resolve(node["properties"][part], base)
    return node


def _schema_for(table: str, key: str) -> dict:
    if table == "tuning":
        if key == "rate_hz":
            return _schema_at(COMMANDS / "set_rate.schema.json", "hz")
        if key == "base_speed":
            return _schema_at(COMMANDS / "set_config.schema.json", "base_speed")
        return _schema_at(COMMANDS / "set_config.schema.json", "params", key)
    return _schema_at(COMMANDS / "set_profile.schema.json", "measured", key)


def _is_integer(schema: dict) -> bool:
    types = schema.get("type")
    return "integer" in (types if isinstance(types, list) else [types])


def _assert_within(name: str, panel: dict, integer: bool, schema: dict) -> None:
    """El conjunto que acepta el panel está contenido en el que acepta el contrato."""
    low = panel.get("min", panel.get("above"))
    if "minimum" in schema:
        assert low is not None and low >= schema["minimum"], f"{name}: el panel acepta menos que minimum {schema['minimum']}"
    if "exclusiveMinimum" in schema:
        bound = schema["exclusiveMinimum"]
        ok = ("above" in panel and panel["above"] >= bound) or ("min" in panel and panel["min"] > bound)
        assert ok, f"{name}: el panel acepta ≤ exclusiveMinimum {bound}"
    if "maximum" in schema:
        assert "max" in panel and panel["max"] <= schema["maximum"], f"{name}: el panel acepta más que maximum {schema['maximum']}"
    if "exclusiveMaximum" in schema:
        assert "max" in panel and panel["max"] < schema["exclusiveMaximum"], f"{name}: el panel acepta ≥ exclusiveMaximum"
    if _is_integer(schema):
        assert integer, f"{name}: el contrato pide entero y el panel acepta decimales"


def _command(table: str, key: str, value: float) -> dict:
    if table == "tuning":
        if key == "rate_hz":
            return {"cmd": "set_rate", "hz": value}
        if key == "base_speed":
            return {"cmd": "set_config", "base_speed": value}
        return {"cmd": "set_config", "params": {key: value}}
    return {"cmd": "set_profile", "measured": {key: value}}


def _edges(bounds: dict, integer: bool) -> tuple[list[float], list[float]]:
    """Valores del borde que el panel debe aceptar y los justo de afuera que debe rechazar."""
    step = 1 if integer else 1e-6
    inside: list[float] = []
    outside: list[float] = []
    if "min" in bounds:
        inside.append(bounds["min"])
        outside.append(bounds["min"] - step)
    if "above" in bounds:
        inside.append(bounds["above"] + step)
        outside.append(bounds["above"])
    if "max" in bounds:
        inside.append(bounds["max"])
        outside.append(bounds["max"] + step)
    else:
        inside.append(1e6 if not integer else 1_000_000)
    return inside, outside


def _text(value: float, integer: bool) -> str:
    return str(int(value)) if integer else repr(float(value))


@pytest.fixture
def tables(page: Page, live_url: str) -> dict:
    page.goto(live_url)
    return page.evaluate(PANEL_TABLES)


def test_panel_ranges_are_never_more_permissive_than_the_contract(tables: dict) -> None:
    assert [c["field"] for c in tables["tuning"]] == ["kp", "ki", "kd", "base_speed", "rate_hz"]
    assert len(tables["profile"]) == 12
    for control in tables["tuning"]:
        _assert_within(control["field"], control["bounds"], control["integer"], _schema_for("tuning", control["field"]))
    for param in tables["profile"]:
        schema = _schema_for("profile", param["key"])
        for bits, bounds in param["bounds"].items():
            _assert_within(f"{param['key']} (adc_bits={bits})", bounds, param["integer"], schema)


def test_adc_parameters_follow_adc_bits(tables: dict) -> None:
    for param in tables["profile"]:
        if param["key"] not in ("adc_white", "adc_black", "adc_noise"):
            assert all(b == param["bounds"]["null"] for b in param["bounds"].values()), param["key"]
            continue
        for bits in ADC_BITS:
            assert param["bounds"][str(bits)]["max"] == 2**bits - 1, (param["key"], bits)


def test_edge_values_are_accepted_or_rejected_like_the_contract(page: Page, tables: dict) -> None:
    cases: list[list] = []
    expected: list[bool] = []
    commands: list[dict] = []
    rows = [("tuning", c["field"], None, c["bounds"], c["integer"]) for c in tables["tuning"]]
    for param in tables["profile"]:
        for bits in (None, 12):
            rows.append(("profile", param["key"], bits, param["bounds"]["null" if bits is None else str(bits)], param["integer"]))
    for table, key, bits, bounds, integer in rows:
        inside, outside = _edges(bounds, integer)
        for value in inside:
            cases.append([table, key, bits, _text(value, integer)])
            expected.append(True)
            commands.append(_command(table, key, int(value) if integer else float(value)))
        for value in outside:
            if math.isfinite(value):
                cases.append([table, key, bits, _text(value, integer)])
                expected.append(False)
        if integer:
            cases.append([table, key, bits, "1.5"])
            expected.append(False)
    accepted = page.evaluate(PANEL_ACCEPTS, cases)
    wrong = [(case, ok) for case, ok, want in zip(cases, accepted, expected) if ok != want]
    assert not wrong, f"el panel acepta o rechaza distinto de lo esperado: {wrong}"
    for command in commands:
        result = validate_command(command)
        assert result.ok, f"el panel acepta un valor que el contrato rechaza: {command} {result.violations}"
