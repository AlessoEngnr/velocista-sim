"""Carga de los JSON Schemas de `contract/schemas/` en un registro en memoria."""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SCHEMA_SUFFIX = ".schema.json"


@dataclass(frozen=True, eq=False)
class SchemaStore:
    """Schemas del contrato indexados por ruta relativa sin sufijo (`"messages/telemetry"`)."""

    schema_dir: Path
    registry: Registry
    schemas: Mapping[str, dict[str, Any]]

    def get(self, name: str) -> dict[str, Any] | None:
        """Devuelve el schema `name` o `None` si no existe."""
        return self.schemas.get(name)

    def __contains__(self, name: object) -> bool:
        return name in self.schemas


def load_schemas(schema_dir: Path | None = None) -> SchemaStore:
    """Carga todos los `*.schema.json` de `schema_dir` (por defecto `contract/schemas/`).

    El resultado se cachea por carpeta: los schemas se leen una sola vez por proceso.
    """
    if schema_dir is None:
        return _load(_default_schema_dir())
    return _load(Path(schema_dir).resolve())


@functools.cache
def _default_schema_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "contract" / "schemas"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "No se encontró la carpeta contract/schemas subiendo desde "
        f"{Path(__file__).resolve().parent}; indique schema_dir explícitamente."
    )


@functools.cache
def _load(schema_dir: Path) -> SchemaStore:
    if not schema_dir.is_dir():
        raise FileNotFoundError(f"La carpeta de schemas no existe: {schema_dir}")
    schemas: dict[str, dict[str, Any]] = {}
    resources: list[tuple[str, Resource]] = []
    for path in sorted(schema_dir.rglob(f"*{SCHEMA_SUFFIX}")):
        contents = json.loads(path.read_text(encoding="utf-8"))
        name = path.relative_to(schema_dir).as_posix().removesuffix(SCHEMA_SUFFIX)
        schemas[name] = contents
        resource = Resource.from_contents(contents, default_specification=DRAFT202012)
        resources.append((contents["$id"], resource))
    registry = Registry().with_resources(resources).crawl()
    return SchemaStore(schema_dir, registry, MappingProxyType(schemas))
