"""Genera una pista track v1 con forma de estadio (por defecto `config/tracks/oval-01.json`).

Uso: `uv run python tools/gen_oval.py [--straight 1.5 --radius 0.6 ...]`. Solo usa la
biblioteca estándar para la geometría; al final valida la pista con el validador del contrato y
termina con error si no es válida. Volver a correrlo con los mismos parámetros reproduce el
archivo byte a byte (research R12).

La `centerline` empieza en el extremo izquierdo de la recta inferior y recorre el estadio en
sentido antihorario, con puntos equiespaciados en longitud de arco cada ≈ 5 mm.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "config" / "tracks" / "oval-01.json"
SAMPLING_M = 0.005
DECIMALS = 6


def stadium_point(s: float, cx: float, cy: float, straight: float, radius: float) -> tuple[float, float]:
    """Punto a la distancia `s` (m) a lo largo del estadio, desde el inicio de la recta inferior."""
    arc = math.pi * radius
    if s < straight:
        return cx - straight / 2 + s, cy - radius
    s -= straight
    if s < arc:
        angle = -math.pi / 2 + s / radius
        return cx + straight / 2 + radius * math.cos(angle), cy + radius * math.sin(angle)
    s -= arc
    if s < straight:
        return cx + straight / 2 - s, cy + radius
    s -= straight
    angle = math.pi / 2 + s / radius
    return cx - straight / 2 + radius * math.cos(angle), cy + radius * math.sin(angle)


def build_track(args: argparse.Namespace) -> dict:
    """Arma la pista track v1 a partir de los parámetros."""
    length = 2 * args.straight + 2 * math.pi * args.radius
    count = round(length / SAMPLING_M)
    step = length / count
    centerline = []
    for index in range(count):
        x, y = stadium_point(index * step, args.cx, args.cy, args.straight, args.radius)
        centerline.append([round(x, DECIMALS) + 0.0, round(y, DECIMALS) + 0.0])
    return {
        "id": args.id,
        "v": 1,
        "name": args.name,
        "units": "m",
        "board": {"width": args.width, "height": args.height},
        "line_width": args.line_width,
        "closed": True,
        "centerline": centerline,
        "gaps": [],
        "start": {"at": args.start_at},
        "rules_profile": args.rules_profile,
    }


def to_json(track: dict) -> str:
    """JSON con `indent=2` y cada punto `[x, y]` en una sola línea."""
    text = json.dumps(track, ensure_ascii=False, indent=2)
    text = re.sub(r"\[\s+(-?[\d.eE+-]+),\s+(-?[\d.eE+-]+)\s+\]", r"[\1, \2]", text)
    return text + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera una pista estadio track v1.")
    parser.add_argument("--id", default="oval-01")
    parser.add_argument("--name", default="Óvalo 3 × 2,5")
    parser.add_argument("--width", type=float, default=3.0, help="ancho del tablero, m")
    parser.add_argument("--height", type=float, default=2.5, help="alto del tablero, m")
    parser.add_argument("--cx", type=float, default=1.5, help="centro x del estadio, m")
    parser.add_argument("--cy", type=float, default=1.25, help="centro y del estadio, m")
    parser.add_argument("--straight", type=float, default=1.5, help="largo de cada recta, m")
    parser.add_argument("--radius", type=float, default=0.6, help="radio de las curvas, m")
    parser.add_argument("--line-width", type=float, default=0.019, help="ancho de la línea, m")
    parser.add_argument("--start-at", type=float, default=0.1, help="salida a lo largo de la línea, m")
    parser.add_argument("--rules-profile", default="lgr2026")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    track = build_track(args)

    sys.path.insert(0, str(REPO_ROOT / "src"))
    from velocista_sim.contract import validate_track

    result = validate_track(track)
    if not result.ok:
        for violation in result.violations[:10]:
            print(f"pista inválida: {violation.rule} {violation.path}: {violation.message}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(to_json(track).encode("utf-8"))
    print(f"{args.output}: {len(track['centerline'])} puntos")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
