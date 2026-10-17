"""Configuración del servidor leída de variables de entorno (contracts/config-files.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


def default_config_dir() -> Path:
    """Carpeta `config/` del repo, buscada subiendo desde este módulo."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "config"
        if (candidate / "robots").is_dir() and (candidate / "tracks").is_dir():
            return candidate
    raise FileNotFoundError(
        "No se encontró la carpeta config/ subiendo desde "
        f"{Path(__file__).resolve().parent}; indique VELOCISTA_CONFIG_DIR."
    )


@dataclass(frozen=True)
class Settings:
    """Parámetros del servidor; ver data-model.md, Settings."""

    port: int = 8000
    seed: int = 1
    config_dir: Path = field(default_factory=default_config_dir)
    max_sessions: int = 20
    default_robot: str = "velocista-01"
    default_track: str = "oval-01"

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "Settings":
        """Construye la configuración desde `environ`; error en español si un valor no es válido."""
        config_dir = environ.get("VELOCISTA_CONFIG_DIR")
        return cls(
            port=_int_var(environ, "PORT", 8000, minimum=1),
            seed=_int_var(environ, "VELOCISTA_SEED", 1, minimum=0),
            config_dir=Path(config_dir) if config_dir else default_config_dir(),
            max_sessions=_int_var(environ, "VELOCISTA_MAX_SESSIONS", 20, minimum=1),
        )


def _int_var(environ: Mapping[str, str], name: str, default: int, minimum: int) -> int:
    raw = environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise ValueError(f"la variable {name} debe ser un número entero; vale {raw!r}") from None
    if value < minimum:
        raise ValueError(f"la variable {name} debe ser un entero ≥ {minimum}; vale {value}")
    return value
