"""Núcleo síncrono de una sesión: pasos, comandos, corridas y mensajes (data-model.md, Session).

No lee el reloj ni hace E/S: el resultado depende solo de la secuencia de pasos y de en qué paso
entra cada comando (principio VI). `Pacer` decide cuándo llamar a `step()`.
"""

from __future__ import annotations

import copy
import logging
import math
import uuid
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Any

from numpy.random import PCG64, Generator, SeedSequence

from velocista_sim.contract import effective_profile, validate_profile
from velocista_sim.robot import PidConfig, Robot, RobotParams
from velocista_sim.world import LapCompleted, OffTrack, TrackGeometry, World, WorldParams

from .catalog import Catalog
from .commands import RANGE_RULES, CommandError, error_message, parse
from .settings import Settings

log = logging.getLogger(__name__)

DT_MS = 2
DEFAULT_RATE_HZ = 50
DECIMALS = 6


@dataclass(frozen=True)
class ControllerConfig:
    """Configuración del controlador; `set_config` produce una nueva combinando campos."""

    controller: str = "pid"
    kp: float = 0.045
    ki: float = 0
    kd: float = 0.9
    base_speed: int = 180

    def merged(self, command: dict[str, Any]) -> "ControllerConfig":
        """Combina los campos de un `set_config` (incluidos los parámetros sueltos de `params`)."""
        params = command.get("params", {})
        return replace(
            self,
            controller=command.get("controller", self.controller),
            kp=params.get("kp", self.kp),
            ki=params.get("ki", self.ki),
            kd=params.get("kd", self.kd),
            base_speed=command.get("base_speed", self.base_speed),
        )

    def to_message(self) -> dict[str, Any]:
        """Forma `{controller, params:{kp,ki,kd}, base_speed}` de `config` y `summary.config`."""
        return {
            "controller": self.controller,
            "params": {"kp": self.kp, "ki": self.ki, "kd": self.kd},
            "base_speed": self.base_speed,
        }

    def pid(self) -> PidConfig:
        return PidConfig(
            kp=float(self.kp), ki=float(self.ki), kd=float(self.kd), base_speed=int(self.base_speed)
        )


@dataclass
class Run:
    """Corrida activa de la sesión."""

    run_id: str
    number: int
    start_config: ControllerConfig
    track_id: str
    lap_start_ms: int
    config_changed: bool = False
    lap_times_ms: list[int] = field(default_factory=list)
    off_tracks: int = 0

    def summary(self, lap_timing: bool) -> dict[str, Any]:
        """`summary` de `run_finished`."""
        times = self.lap_times_ms
        return {
            "laps": len(times) if lap_timing else None,
            "best_lap_ms": min(times) if lap_timing and times else None,
            "avg_lap_ms": round(sum(times) / len(times)) if lap_timing and times else None,
            "off_tracks": self.off_tracks,
            "track_id": self.track_id,
            "config": self.start_config.to_message(),
            "config_changed": self.config_changed,
        }


_GEOMETRIES: dict[int, tuple[dict, TrackGeometry]] = {}


def geometry_for(track: dict) -> TrackGeometry:
    """Geometría precalculada de `track`; se reutiliza para el mismo objeto de pista."""
    cached = _GEOMETRIES.get(id(track))
    if cached is not None and cached[0] is track:
        return cached[1]
    geometry = TrackGeometry.from_track(track)
    _GEOMETRIES[id(track)] = (track, geometry)
    return geometry


def _robot_params(effective: dict) -> RobotParams:
    return RobotParams(
        line_sensors=int(effective["line_sensors"]),
        adc_white=int(effective["adc_white"]),
        adc_black=int(effective["adc_black"]),
        control_period_ms=float(effective["control_period_ms"]),
    )


class Session:
    """Una sesión por conexión: mundo, robot, corrida y calendarios propios."""

    def __init__(self, catalog: Catalog, settings: Settings,
                 robot_id: str | None = None, track_id: str | None = None) -> None:
        self.catalog = catalog
        self.settings = settings
        self.session_id = "s-" + uuid.uuid4().hex[:8]
        self.seed = settings.seed
        self._idle_rng = Generator(PCG64(SeedSequence([self.seed, 0])))
        self.rng = self._idle_rng
        self.step_index = 0
        self.seq = 0
        self.inbox: deque[str] = deque()
        self.session_tracks: dict[str, dict] = {}
        self.run: Run | None = None
        self.run_counter = 0

        self._unknown: list[tuple[str, str]] = []
        if robot_id is not None and robot_id not in catalog.profiles:
            self._unknown.append((
                "unknown_robot",
                f"el robot «{robot_id}» no está en el catálogo; se usa {settings.default_robot}",
            ))
            robot_id = None
        if track_id is not None and track_id not in catalog.tracks:
            self._unknown.append((
                "unknown_track",
                f"la pista «{track_id}» no está en el catálogo; se usa {settings.default_track}",
            ))
            track_id = None
        self.profile = copy.deepcopy(catalog.profiles[robot_id or settings.default_robot])
        self.effective = effective_profile(self.profile)
        self.track = catalog.tracks[track_id or settings.default_track]
        self.config = ControllerConfig()
        self.rate_hz = DEFAULT_RATE_HZ
        self.rate_anchor_ms = 0
        self.rate_tick = 1

        self.world = World(WorldParams.from_effective(self.effective), geometry_for(self.track))
        self.robot = Robot(_robot_params(self.effective), self.config.pid())
        self.control_anchor_ms = 0
        self.control_tick = 0
        self.last_sensors: list[int] = [int(self.effective["adc_white"])] * int(self.effective["line_sensors"])
        self.hello = self._hello_message(0)

    # --- Interfaz -------------------------------------------------------------------------

    @property
    def t_ms(self) -> int:
        """Tiempo simulado de la sesión, ms."""
        return self.step_index * DT_MS

    def open(self) -> list[dict]:
        """Mensajes de apertura con `t_ms = 0`: `hello`, `config` y, si los parámetros de conexión
        `robot`/`track` no existían, `error unknown_robot` y/o `unknown_track` (FR-037)."""
        self._log_profile("apertura")
        opening = [self.hello, self._config_message(0)]
        opening += [
            error_message(CommandError(code, None, message), 0) for code, message in self._unknown
        ]
        return opening

    def submit(self, frame: str) -> None:
        """Encola un frame recibido; se aplica al inicio del próximo paso (FR-032)."""
        self.inbox.append(frame)

    def step(self) -> list[dict]:
        """Ejecuta un paso de `dt = 2 ms` y devuelve los mensajes emitidos, en orden."""
        t_start = self.t_ms
        emitted: list[dict] = []
        while self.inbox:
            emitted += self._handle(self.inbox.popleft(), t_start)

        if self._control_due(t_start):
            self.last_sensors = self.world.read_sensors(self.rng)
            output = self.robot.tick(self.last_sensors, self.run is not None)
            self.world.set_motor_pwm(output.left, output.right)

        self.world.step()
        self.step_index += 1
        t_ms = self.t_ms

        if self.run is not None:
            for world_event in self.world.detect(t_ms):
                emitted += self._on_world_event(world_event, t_ms)

        if (t_ms - self.rate_anchor_ms) * self.rate_hz >= self.rate_tick * 1000:
            self.rate_tick += 1
            emitted.append(self._telemetry_message(t_ms))
        return emitted

    def next_telemetry_step(self) -> int:
        """Índice de paso tras el cual se emitirá la próxima `telemetry`."""
        needed = self.rate_tick * 1000 + self.rate_anchor_ms * self.rate_hz
        return -(-needed // (DT_MS * self.rate_hz))

    # --- Calendarios ----------------------------------------------------------------------

    def _control_due(self, t_ms: int) -> bool:
        period = float(self.effective["control_period_ms"])
        if t_ms < self.control_anchor_ms + self.control_tick * period:
            return False
        self.control_tick = math.floor((t_ms - self.control_anchor_ms) / period) + 1
        return True

    def _restart_control(self, t_ms: int) -> None:
        self.control_anchor_ms = t_ms
        self.control_tick = 0

    # --- Comandos -------------------------------------------------------------------------

    def _handle(self, frame: str, t_ms: int) -> list[dict]:
        parsed = parse(frame)
        if isinstance(parsed, CommandError):
            return [error_message(parsed, t_ms)]
        handler = getattr(self, f"_cmd_{parsed.cmd}")
        return handler(parsed.fields, t_ms)

    def _reject(self, code: str, cmd: str, message: str, t_ms: int) -> list[dict]:
        return [error_message(CommandError(code, cmd, message), t_ms)]

    def _run_active(self, cmd: str, t_ms: int) -> list[dict]:
        return self._reject("run_active", cmd, f"{cmd} no se acepta con una corrida activa", t_ms)

    def _cmd_start(self, fields: dict, t_ms: int) -> list[dict]:
        if self.run is not None:
            return self._run_active("start", t_ms)
        self.run_counter += 1
        number = self.run_counter
        self.run = Run(
            run_id=f"r-{number}", number=number, start_config=self.config,
            track_id=self.track["id"], lap_start_ms=t_ms,
        )
        self.world.reset_to_start()
        self.robot.reset()
        self.world.set_motor_pwm(0, 0)
        self.rng = Generator(PCG64(SeedSequence([self.seed, number])))
        self.world.begin_run(t_ms)
        self._restart_control(t_ms)
        return [self._event(t_ms, "run_started")]

    def _cmd_stop(self, fields: dict, t_ms: int) -> list[dict]:
        if self.run is None:
            return self._reject("no_run", "stop", "stop sin una corrida activa", t_ms)
        return [self._finish(t_ms)]

    def _cmd_set_config(self, fields: dict, t_ms: int) -> list[dict]:
        self.config = self.config.merged(fields)
        self.robot.set_config(self.config.pid())
        if self.run is not None:
            self.run.config_changed = True
        return [self._config_message(t_ms)]

    def _cmd_set_rate(self, fields: dict, t_ms: int) -> list[dict]:
        self.rate_hz = fields["hz"]
        self.rate_anchor_ms = t_ms
        self.rate_tick = 1
        return [self._config_message(t_ms)]

    def _cmd_list(self, fields: dict, t_ms: int) -> list[dict]:
        tracks = list(self.catalog.tracks)
        tracks += [track_id for track_id in self.session_tracks if track_id not in self.catalog.tracks]
        return [{"type": "catalog", "v": 1, "t_ms": t_ms,
                 "robots": list(self.catalog.profiles), "tracks": tracks}]

    def _cmd_reset(self, fields: dict, t_ms: int) -> list[dict]:
        if self.run is not None:
            return self._run_active("reset", t_ms)
        self._robot_to_start()
        return []

    def _cmd_load(self, fields: dict, t_ms: int) -> list[dict]:
        if self.run is not None:
            return self._run_active("load", t_ms)
        robot_id = fields["robot_id"]
        if robot_id not in self.catalog.profiles:
            return self._reject(
                "unknown_robot", "load", f"el robot «{robot_id}» no está en el catálogo", t_ms
            )
        self.profile = copy.deepcopy(self.catalog.profiles[robot_id])
        self._apply_profile(t_ms)
        self._robot_to_start()
        self.hello = self._hello_message(t_ms)
        self._log_profile("load")
        return [self.hello, self._config_message(t_ms)]

    def _cmd_set_profile(self, fields: dict, t_ms: int) -> list[dict]:
        if self.run is not None:
            return self._run_active("set_profile", t_ms)
        candidate = copy.deepcopy(self.profile)
        for name, value in fields["measured"].items():
            if not isinstance(candidate.get(name), dict):
                return self._reject(
                    "invalid_params", "set_profile", f"el perfil no tiene el parámetro «{name}»", t_ms
                )
            candidate[name]["measured"] = value
        result = validate_profile(candidate)
        if not result.ok:
            violation = result.violations[0]
            in_range = all(v.rule in RANGE_RULES for v in result.violations)
            message = f"set_profile: perfil inválido: {violation.message} (en «{violation.path}»)"
            return self._reject("out_of_range" if in_range else "invalid_params", "set_profile", message, t_ms)
        self.profile = candidate
        self._apply_profile(t_ms)
        self._log_profile("set_profile")
        return [self._config_message(t_ms)]

    def _cmd_load_track(self, fields: dict, t_ms: int) -> list[dict]:
        if self.run is not None:
            return self._run_active("load_track", t_ms)
        track = fields["track"]
        geometry = TrackGeometry.from_track(track)
        self.session_tracks[track["id"]] = track
        self.track = track
        self.world.set_track(geometry)
        self._robot_to_start()
        return [self._config_message(t_ms)]

    def _apply_profile(self, t_ms: int) -> None:
        """Recalcula el perfil efectivo y los parámetros de mundo y robot, sin mover el robot."""
        self.effective = effective_profile(self.profile)
        self.world.set_params(WorldParams.from_effective(self.effective))
        self.robot.set_params(_robot_params(self.effective))
        self._restart_control(t_ms)
        if len(self.last_sensors) != int(self.effective["line_sensors"]):
            self.last_sensors = [int(self.effective["adc_white"])] * int(self.effective["line_sensors"])

    # --- Corrida --------------------------------------------------------------------------

    def _on_world_event(self, world_event: LapCompleted | OffTrack, t_ms: int) -> list[dict]:
        run = self.run
        if run is None:
            return []
        if isinstance(world_event, LapCompleted):
            run.lap_times_ms.append(world_event.lap_ms)
            run.lap_start_ms = t_ms
            if not self._lap_timing:
                return []
            return [self._event(t_ms, "lap", lap=world_event.lap, lap_ms=world_event.lap_ms)]
        run.off_tracks += 1
        off_track = self._event(t_ms, "off_track", reason=world_event.reason)
        return [off_track, self._finish(t_ms)]

    def _finish(self, t_ms: int) -> dict:
        """Termina la corrida activa: `run_finished`, motores a 0 y vuelta al generador ocioso."""
        run = self.run
        assert run is not None
        message = self._event(t_ms, "run_finished", summary=run.summary(self._lap_timing))
        self.run = None
        self.world.end_run()
        self.world.set_motor_pwm(0, 0)
        self.robot.tick(self.last_sensors, running=False)
        self.rng = self._idle_rng
        return message

    def _robot_to_start(self) -> None:
        self.world.reset_to_start()
        self.robot.reset()
        self.robot.tick(self.last_sensors, running=False)

    # --- Mensajes -------------------------------------------------------------------------

    @property
    def _lap_timing(self) -> bool:
        return self.effective["lap_timing"] is True

    def _event(self, t_ms: int, name: str, **fields: Any) -> dict:
        assert self.run is not None
        return {"type": "event", "v": 1, "t_ms": t_ms, "event": name, "run_id": self.run.run_id, **fields}

    def _hello_message(self, t_ms: int) -> dict:
        e = self.effective
        return {
            "type": "hello", "v": 1, "t_ms": t_ms, "session_id": self.session_id, "source": "sim",
            "robot": {"id": e["id"], "firmware": e["firmware"], "hw_rev": e["hw_rev"]},
            "capabilities": {
                "line_sensors": e["line_sensors"], "adc_bits": e["adc_bits"], "motors": e["motors"],
                "turbine": e["turbine"], "encoders": e["encoders"], "imu": e["imu"],
                "lap_timing": e["lap_timing"],
                "battery": {
                    "cells": e["battery_cells"], "nominal_v": e["battery_nominal_v"],
                    "voltage_sense": e["battery_voltage_sense"],
                },
            },
        }

    def _config_message(self, t_ms: int) -> dict:
        return {"type": "config", "v": 1, "t_ms": t_ms, **self.config.to_message(),
                "rate_hz": self.rate_hz, "track_id": self.track["id"]}

    def _telemetry_message(self, t_ms: int) -> dict:
        output = self.robot.last_output
        message: dict[str, Any] = {"type": "telemetry", "v": 1, "t_ms": t_ms, "seq": self.seq,
                                   "running": self.run is not None}
        self.seq += 1
        if self.run is not None:
            message["run_id"] = self.run.run_id
        message.update({
            "sensors": list(self.last_sensors),
            "line_position": output.line_position,
            "line_lost": output.line_lost,
            "error": output.error,
            "control": {"p": round(output.p, DECIMALS), "i": round(output.i, DECIMALS),
                        "d": round(output.d, DECIMALS), "out": round(output.out, DECIMALS)},
            "motors": {"left": output.left, "right": output.right},
        })
        if self.run is not None and self._lap_timing:
            message["lap"] = {"n": len(self.run.lap_times_ms), "current_ms": t_ms - self.run.lap_start_ms}
        if self.effective["battery_voltage_sense"] is True:
            message["battery_v"] = self.world.battery_v()
        message["sim_truth"] = self.world.truth()
        return message

    def _log_profile(self, reason: str) -> None:
        """Registra el perfil efectivo con el origen de cada valor (principio V)."""
        parts = []
        for name, param in self.profile.items():
            if not isinstance(param, dict) or "default" not in param:
                continue
            origin = "default" if param.get("measured") is None else "measured"
            parts.append(f"{name}={self.effective[name]!r} ({origin}, {param.get('source')})")
        log.info("sesión %s (%s): perfil efectivo: %s", self.session_id, reason, "; ".join(parts))
