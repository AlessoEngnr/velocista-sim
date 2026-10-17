"""Catálogo de perfiles y pistas de `config/` (research R12, contracts/config-files.md)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from velocista_sim.contract import effective_profile, validate_profile, validate_track

from .settings import Settings


class CatalogError(Exception):
    """El catálogo no es válido: el servidor no debe arrancar."""


@dataclass(frozen=True)
class Catalog:
    """Perfiles (`robot-profile`) y pistas (track v1) por `id`; inmutable y compartido."""

    profiles: Mapping[str, dict]
    tracks: Mapping[str, dict]


def load_catalog(config_dir: Path, settings: Settings) -> Catalog:
    """Lee y valida `robots/*.json` y `tracks/*.json`; levanta `CatalogError` si algo falla."""
    config_dir = Path(config_dir)
    profiles: dict[str, dict] = {}
    for path in sorted((config_dir / "robots").glob("*.json")):
        profile = _read(path)
        _check(path, validate_profile(profile))
        _check_name(path, profile["id"]["default"])
        _check_simulable(path, profile)
        profiles[path.stem] = profile

    tracks: dict[str, dict] = {}
    for path in sorted((config_dir / "tracks").glob("*.json")):
        track = _read(path)
        _check(path, validate_track(track))
        _check_name(path, track["id"])
        tracks[path.stem] = track

    if settings.default_robot not in profiles:
        raise CatalogError(
            f"falta el perfil por defecto «{settings.default_robot}» en {config_dir / 'robots'}"
        )
    if settings.default_track not in tracks:
        raise CatalogError(
            f"falta la pista por defecto «{settings.default_track}» en {config_dir / 'tracks'}"
        )
    return Catalog(MappingProxyType(profiles), MappingProxyType(tracks))


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CatalogError(f"{path}: no se pudo leer como JSON ({exc})") from exc


def _check(path: Path, result) -> None:
    if not result.ok:
        first = result.violations[0]
        raise CatalogError(f"{path}: regla «{first.rule}» en «{first.path}»: {first.message}")


def _check_name(path: Path, item_id: object) -> None:
    if path.stem != item_id:
        raise CatalogError(f"{path}: el nombre del archivo debe ser igual al id ({item_id!r})")


def _check_simulable(path: Path, profile: dict) -> None:
    """El simulador v1 solo simula 2 motores, sin encoders, IMU ni turbina."""
    effective = effective_profile(profile)
    if effective.get("motors") != 2:
        raise CatalogError(f"{path}: el simulador v1 necesita motors = 2")
    for name in ("encoders", "imu", "turbine"):
        if effective.get(name) is not False:
            raise CatalogError(f"{path}: el simulador v1 no simula «{name}»; debe valer false")
