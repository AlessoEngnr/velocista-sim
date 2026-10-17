"""Reglas de arquitectura: el robot no conoce el mundo y la simulación no lee el reloj.

Principios III y VI de la constitución (research R2).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "src" / "velocista_sim"

FORBIDDEN_STDLIB = {"time", "datetime", "random", "asyncio"}
FORBIDDEN_PACKAGES = {
    "world": {"velocista_sim.robot", "velocista_sim.server"},
    "robot": {"velocista_sim.world", "velocista_sim.server"},
}


def _imported_modules(path: Path) -> set[str]:
    """Módulos que importa `path`, con los imports relativos resueltos a nombre absoluto."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    relative_parts = path.relative_to(PACKAGE_DIR.parent).with_suffix("").parts
    current_package = list(relative_parts[:-1])
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = current_package[: len(current_package) - node.level + 1]
                prefix = ".".join(base)
                name = f"{prefix}.{node.module}" if node.module else prefix
                modules.add(name)
                if not node.module:
                    modules.update(f"{prefix}.{alias.name}" for alias in node.names)
            elif node.module:
                modules.add(node.module)
    return modules


def _files(package: str) -> list[Path]:
    return sorted((PACKAGE_DIR / package).rglob("*.py"))


@pytest.mark.parametrize("package", sorted(FORBIDDEN_PACKAGES))
def test_package_has_sources(package: str) -> None:
    assert _files(package), f"el paquete {package} no tiene archivos .py"


@pytest.mark.parametrize("package", sorted(FORBIDDEN_PACKAGES))
def test_no_forbidden_imports(package: str) -> None:
    problems: list[str] = []
    for path in _files(package):
        for module in _imported_modules(path):
            root = module.split(".")[0]
            if root in FORBIDDEN_STDLIB:
                problems.append(f"{path.name} importa {module} (reloj, RNG global o asyncio)")
            for forbidden in FORBIDDEN_PACKAGES[package]:
                if module == forbidden or module.startswith(forbidden + "."):
                    problems.append(f"{path.name} importa {module}")
    assert not problems, "imports prohibidos en " + package + ":\n" + "\n".join(problems)
