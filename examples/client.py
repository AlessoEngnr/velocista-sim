# /// script
# requires-python = ">=3.12"
# dependencies = ["websockets>=15"]
# ///
"""Cliente de ejemplo de velocista-sim (contracts/client-cli.md).

Corre una configuración del PID y muestra el resumen de la corrida. No necesita el repositorio:

    uv run examples/client.py ws://localhost:8000/ws --kp 0.045 --kd 0.9 --laps 3

Códigos de salida: 0 corrida terminada; 1 error de conexión; 2 el servidor rechazó un comando.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from urllib.parse import urlencode

from websockets.asyncio.client import connect
from websockets.exceptions import InvalidHandshake, InvalidURI, WebSocketException

FINISH_GRACE_S = 10.0


class Rejected(Exception):
    """El servidor respondió `error` a un comando."""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Corre una configuración en velocista-sim y muestra el resumen.")
    parser.add_argument("url", nargs="?", default="ws://localhost:8000/ws", help="URL del WebSocket")
    parser.add_argument("--kp", type=float, default=0.045)
    parser.add_argument("--ki", type=float, default=0.0)
    parser.add_argument("--kd", type=float, default=0.9)
    parser.add_argument("--base-speed", type=int, default=180, help="PWM base 0–255")
    parser.add_argument("--laps", type=int, default=3, help="envía stop al completar N vueltas")
    parser.add_argument("--timeout", type=float, default=30.0, help="segundos máximos de corrida")
    parser.add_argument("--robot", help="perfil de robot del catálogo")
    parser.add_argument("--track", help="pista del catálogo")
    return parser.parse_args(argv)


def connection_url(args: argparse.Namespace) -> str:
    query = {key: value for key, value in (("robot", args.robot), ("track", args.track)) if value}
    if not query:
        return args.url
    return args.url + ("&" if "?" in args.url else "?") + urlencode(query)


def seconds(ms: int | None) -> str:
    return "-" if ms is None else f"{ms / 1000:.3f} s"


def show_config(config: dict) -> str:
    params = config.get("params", {})
    return (f"{config.get('controller')} kp={params.get('kp')} ki={params.get('ki')} kd={params.get('kd')} "
            f"base_speed={config.get('base_speed')}")


def show_summary(run_id: str, summary: dict) -> None:
    print(f"summary {run_id}:")
    print(f"  laps (vueltas): {summary.get('laps')}")
    print(f"  best_lap (mejor vuelta): {seconds(summary.get('best_lap_ms'))}")
    print(f"  avg_lap (promedio): {seconds(summary.get('avg_lap_ms'))}")
    print(f"  off_tracks (salidas de pista): {summary.get('off_tracks')}")
    print(f"  track_id (pista): {summary.get('track_id')}")
    print(f"  config: {show_config(summary.get('config', {}))}")
    print(f"  config_changed: {'sí' if summary.get('config_changed') else 'no'}")


async def receive(ws, deadline: float | None = None) -> dict:
    """Próximo mensaje JSON; `TimeoutError` si pasa `deadline` (reloj monótono)."""
    while True:
        timeout = None if deadline is None else max(deadline - time.monotonic(), 0.0)
        raw = await asyncio.wait_for(ws.recv(), timeout)
        try:
            message = json.loads(raw)
        except ValueError:
            continue
        if isinstance(message, dict):
            return message


async def wait_reply(ws, accepted: set[str], cmd: str) -> dict:
    """Espera la respuesta a `cmd`: un mensaje de tipo/evento en `accepted` o un `error`."""
    while True:
        message = await receive(ws)
        if message.get("type") == "error":
            raise Rejected(f"{cmd} rechazado: {message.get('code')}: {message.get('message')}")
        if message.get("type") in accepted or message.get("event") in accepted:
            return message


async def run(args: argparse.Namespace) -> int:
    async with connect(connection_url(args), open_timeout=10) as ws:
        hello = await wait_reply(ws, {"hello"}, "conexión")
        robot = hello.get("robot", {})
        print(f"hello: robot {robot.get('id')} ({robot.get('firmware')}), source {hello.get('source')}, "
              f"sesión {hello.get('session_id')}")
        config = await wait_reply(ws, {"config"}, "conexión")
        print(f"config: {show_config(config)} rate_hz={config.get('rate_hz')} track_id={config.get('track_id')}")
        while True:  # errores de conexión (robot/track inexistentes) llegan tras config
            pass_through = await receive(ws)
            if pass_through.get("type") == "error":
                print(f"aviso: {pass_through.get('code')}: {pass_through.get('message')}")
                continue
            break

        await ws.send(json.dumps({"cmd": "set_config", "v": 1,
                                  "params": {"kp": args.kp, "ki": args.ki, "kd": args.kd},
                                  "base_speed": args.base_speed}))
        config = await wait_reply(ws, {"config"}, "set_config")
        print(f"config: {show_config(config)}")

        await ws.send(json.dumps({"cmd": "start", "v": 1}))
        started = await wait_reply(ws, {"run_started"}, "start")
        print(f"event run_started {started.get('run_id')}")
        deadline = time.monotonic() + args.timeout
        stop_sent = False
        laps = 0
        while True:
            try:
                message = await receive(ws, deadline)
            except TimeoutError:
                if stop_sent:
                    raise
                print(f"timeout de {args.timeout:g} s: se envía stop")
                await ws.send(json.dumps({"cmd": "stop", "v": 1}))
                stop_sent = True
                deadline = time.monotonic() + FINISH_GRACE_S
                continue
            if message.get("type") != "event":
                continue
            event = message.get("event")
            if event == "lap":
                laps += 1
                print(f"event lap {message.get('lap')}: {seconds(message.get('lap_ms'))}")
                if laps >= args.laps and not stop_sent:
                    await ws.send(json.dumps({"cmd": "stop", "v": 1}))
                    stop_sent = True
                    deadline = time.monotonic() + FINISH_GRACE_S
            elif event == "off_track":
                print(f"event off_track: {message.get('reason')}")
            elif event == "run_finished":
                show_summary(message.get("run_id", ""), message.get("summary", {}))
                return 0


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
    args = parse_args(argv)
    try:
        return asyncio.run(run(args))
    except Rejected as exc:
        print(f"error: {exc}")
        return 2
    except (OSError, InvalidURI, InvalidHandshake, TimeoutError) as exc:
        print(f"No se pudo conectar con {args.url}: {exc}", file=sys.stderr)
        return 1
    except WebSocketException as exc:
        print(f"Se cortó la conexión con {args.url}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
