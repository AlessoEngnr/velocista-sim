"""Todo constructor de `static/js/commands.js` produce comandos válidos del contrato v1
(FR-037, SC-004, research R13)."""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import Page

from velocista_sim.contract import validate_command

REPO_ROOT = Path(__file__).resolve().parents[2]
OVAL_01 = REPO_ROOT / "config" / "tracks" / "oval-01.json"

# Casos por función exportada: lista de argumentos de cada llamada.
BUILD_CASES = """
async (track) => {
  const module = await import("/js/commands.js");
  const cases = {
    start: [[]],
    stop: [[]],
    reset: [[]],
    setConfig: [[{ kp: 0.05 }], [{ ki: 0.001 }], [{ kd: 0.9 }], [{ base_speed: 180.4 }], [{ base_speed: 300 }]],
    setRate: [[10], [100]],
    list: [[]],
    load: [["velocista-01"]],
    setProfile: [[{ wheelbase_m: 0.128 }], [{ adc_white: 185 }], [{ wheelbase_m: null }]],
    loadTrack: [[track]],
  };
  const built = {};
  for (const [name, calls] of Object.entries(cases)) {
    built[name] = typeof module[name] === "function" ? calls.map((args) => module[name](...args)) : null;
  }
  return { exported: Object.keys(module), built };
}
"""


def test_every_command_builder_is_valid(page: Page, live_url: str) -> None:
    page.goto(live_url)
    track = json.loads(OVAL_01.read_text(encoding="utf-8"))
    result = page.evaluate(BUILD_CASES, track)

    exported, built = set(result["exported"]), result["built"]
    assert exported == set(built), f"funciones sin caso de prueba o casos sin función: {exported ^ set(built)}"

    problems: list[str] = []
    for name, commands in built.items():
        for command in commands:
            outcome = validate_command(command)
            if not outcome.ok:
                problems.append(f"{name} → {command}: {outcome.violations}")
    assert not problems, "\n".join(problems)


def test_builders_produce_the_documented_shape(page: Page, live_url: str) -> None:
    page.goto(live_url)
    built = page.evaluate(BUILD_CASES, {"id": "x"})["built"]
    assert built["start"] == [{"cmd": "start"}]
    assert built["setConfig"][0] == {"cmd": "set_config", "params": {"kp": 0.05}}
    assert built["setConfig"][3] == {"cmd": "set_config", "base_speed": 180}
    assert built["setConfig"][4] == {"cmd": "set_config", "base_speed": 255}
    assert built["setRate"] == [{"cmd": "set_rate", "hz": 10}, {"cmd": "set_rate", "hz": 100}]
    assert built["load"] == [{"cmd": "load", "robot_id": "velocista-01"}]
    assert built["setProfile"][2] == {"cmd": "set_profile", "measured": {"wheelbase_m": None}}
    assert built["loadTrack"] == [{"cmd": "load_track", "track": {"id": "x"}}]
