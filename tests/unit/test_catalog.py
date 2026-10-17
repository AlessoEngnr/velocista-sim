"""Catálogo de `config/`: carga real y casos que deben impedir el arranque."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from velocista_sim.server.catalog import CatalogError, load_catalog
from velocista_sim.server.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
PROFILE_EXAMPLE = REPO_ROOT / "contract" / "examples" / "valid" / "robot-profile" / "velocista-01-default.json"


def _settings(config_dir: Path) -> Settings:
    return Settings(config_dir=config_dir)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def config_copy(tmp_path: Path) -> Path:
    target = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, target)
    return target


def test_real_catalog_loads() -> None:
    catalog = load_catalog(CONFIG_DIR, _settings(CONFIG_DIR))
    assert "velocista-01" in catalog.profiles
    assert "oval-01" in catalog.tracks


def test_profile_matches_contract_example() -> None:
    assert _read(CONFIG_DIR / "robots" / "velocista-01.json") == _read(PROFILE_EXAMPLE)["message"]


def test_default_config_dir_is_found() -> None:
    assert Settings().config_dir.resolve() == CONFIG_DIR.resolve()


def test_file_name_must_match_id(config_copy: Path) -> None:
    shutil.copy(config_copy / "robots" / "velocista-01.json", config_copy / "robots" / "otro.json")
    with pytest.raises(CatalogError, match="nombre del archivo"):
        load_catalog(config_copy, _settings(config_copy))


def test_profile_with_encoders_is_rejected(config_copy: Path) -> None:
    path = config_copy / "robots" / "velocista-01.json"
    profile = _read(path)
    profile["encoders"]["measured"] = True
    profile["encoder_ticks_per_rev"]["measured"] = 360
    path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(CatalogError, match="encoders"):
        load_catalog(config_copy, _settings(config_copy))


def test_invalid_track_is_rejected(config_copy: Path) -> None:
    path = config_copy / "tracks" / "oval-01.json"
    track = _read(path)
    bad = copy.deepcopy(track)
    bad["centerline"][10] = [9.0, 9.0]
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(CatalogError, match="oval-01.json"):
        load_catalog(config_copy, _settings(config_copy))


def test_missing_default_track_is_rejected(config_copy: Path) -> None:
    (config_copy / "tracks" / "oval-01.json").unlink()
    with pytest.raises(CatalogError, match="oval-01"):
        load_catalog(config_copy, _settings(config_copy))


def test_missing_default_robot_is_rejected(config_copy: Path) -> None:
    (config_copy / "robots" / "velocista-01.json").unlink()
    with pytest.raises(CatalogError, match="velocista-01"):
        load_catalog(config_copy, _settings(config_copy))


def test_settings_from_env() -> None:
    settings = Settings.from_env({"PORT": "9000", "VELOCISTA_SEED": "7", "VELOCISTA_MAX_SESSIONS": "3"})
    assert (settings.port, settings.seed, settings.max_sessions) == (9000, 7, 3)
    assert Settings.from_env({}).port == 8000


@pytest.mark.parametrize("env", [{"PORT": "abc"}, {"VELOCISTA_MAX_SESSIONS": "0"}, {"VELOCISTA_SEED": "1.5"}])
def test_settings_rejects_bad_values(env: dict) -> None:
    with pytest.raises(ValueError, match="variable"):
        Settings.from_env(env)
