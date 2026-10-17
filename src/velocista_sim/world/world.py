"""Mundo simulado: pose verdadera, física, regleta y detección de vueltas y salidas (FR-010 a FR-016).

El mundo no conoce al robot: recibe PWM y entrega lecturas ADC. Toda aleatoriedad entra por el
`rng` que pasa la sesión (principio VI).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from .params import WorldParams
from .physics import PhysicsState, battery_voltage, step_physics
from .sensors import coverage, readings, sensor_positions
from .track import TrackGeometry

LOST_DISTANCE_M = 0.10
LOST_TIME_MS = 1000


@dataclass(frozen=True)
class LapCompleted:
    """Se completó la vuelta `lap` de la corrida, en `lap_ms` ms simulados."""

    lap: int
    lap_ms: int


@dataclass(frozen=True)
class OffTrack:
    """El robot salió de la pista; en v1 siempre por pérdida de línea."""

    reason: str = "line_lost"


class World:
    """Estado físico de una sesión: un robot sobre una pista."""

    DT_S: ClassVar[float] = 0.002
    DT_MS: ClassVar[int] = 2

    def __init__(self, params: WorldParams, track: TrackGeometry) -> None:
        self.params = params
        self.track = track
        self.state = PhysicsState()
        self.pwm_left = 0
        self.pwm_right = 0
        self._coverage_pose: tuple[float, float, float] | None = None
        self._coverage = np.zeros(params.line_sensors)
        self._active = False
        self.progress_s = 0.0
        self.proj_s = 0.0
        self.proj_index: int | None = None
        self.laps_done = 0
        self.lap_start_ms = 0
        self.lost_distance_m = 0.0
        self.lost_time_ms = 0
        self.reset_to_start()

    # --- Configuración ------------------------------------------------------------------

    def set_params(self, params: WorldParams) -> None:
        """Cambia los parámetros físicos sin mover el robot."""
        self.params = params
        self._coverage_pose = None

    def set_track(self, track: TrackGeometry) -> None:
        """Cambia la pista y deja el robot en su salida."""
        self.track = track
        self._coverage_pose = None
        self.reset_to_start()

    def set_pose(self, x: float, y: float, theta: float) -> None:
        """Ubica el eje del robot en (x, y) con rumbo `theta`, sin cambiar sus velocidades."""
        self.state.x, self.state.y, self.state.theta = float(x), float(y), float(theta)

    def reset_to_start(self) -> None:
        """Robot detenido sobre `start.at`, orientado por la tangente; contadores a 0."""
        x, y, heading = self.track.pose_at(self.track.start_s)
        self.state = PhysicsState(x=x, y=y, theta=heading)
        self.pwm_left = self.pwm_right = 0
        self._active = False
        self.progress_s = 0.0
        self.proj_index = None
        self.laps_done = 0
        self.lost_distance_m = 0.0
        self.lost_time_ms = 0

    # --- Paso -----------------------------------------------------------------------------

    def set_motor_pwm(self, left: int, right: int) -> None:
        self.pwm_left, self.pwm_right = int(left), int(right)

    def read_sensors(self, rng: np.random.Generator) -> list[int]:
        """Lecturas ADC de la regleta en la pose actual, con ruido de `rng`."""
        return readings(self._current_coverage(), self.params, rng)

    def sees_ink(self) -> bool:
        """`True` si algún sensor tiene cobertura > 0 (verdad sin ruido)."""
        return bool((self._current_coverage() > 0).any())

    def step(self) -> None:
        """Un paso de física de `DT_S`."""
        step_physics(self.state, self.pwm_left, self.pwm_right, self.params, self.DT_S)

    # --- Corrida y detección ------------------------------------------------------------

    def begin_run(self, t_ms: int) -> None:
        """Arranca el progreso, las vueltas y la detección de salida desde la pose actual."""
        self._active = True
        self.proj_s, self.proj_index = self.track.project(self.state.x, self.state.y)
        self.progress_s = 0.0
        self.laps_done = 0
        self.lap_start_ms = t_ms
        self.lost_distance_m = 0.0
        self.lost_time_ms = 0

    def end_run(self) -> None:
        """Detiene la detección (la corrida terminó)."""
        self._active = False

    def detect(self, t_ms: int) -> list[LapCompleted | OffTrack]:
        """Vueltas completadas y salida de pista tras el último paso (solo con corrida)."""
        if not self._active:
            return []
        events: list[LapCompleted | OffTrack] = []
        state = self.state

        s, self.proj_index = self.track.project(state.x, state.y, self.proj_index)
        delta = s - self.proj_s
        if self.track.closed:
            half = self.track.length / 2
            if delta > half:
                delta -= self.track.length
            elif delta <= -half:
                delta += self.track.length
        self.proj_s = s
        self.progress_s += delta
        if self.track.closed and self.progress_s >= (self.laps_done + 1) * self.track.length:
            self.laps_done += 1
            events.append(LapCompleted(self.laps_done, t_ms - self.lap_start_ms))
            self.lap_start_ms = t_ms

        width, height = self.track.board
        if not (0 <= state.x <= width and 0 <= state.y <= height):
            events.append(OffTrack())
        elif self.sees_ink():
            self.lost_distance_m = 0.0
            self.lost_time_ms = 0
        else:
            self.lost_distance_m += (abs(state.speed) + abs(state.omega) * self.params.sensor_offset_m) * self.DT_S
            self.lost_time_ms += self.DT_MS
            if self.lost_distance_m > LOST_DISTANCE_M or self.lost_time_ms > LOST_TIME_MS:
                events.append(OffTrack())
        if events and isinstance(events[-1], OffTrack):
            self._active = False
        return events

    # --- Verdad ---------------------------------------------------------------------------

    def truth(self) -> dict[str, float]:
        """Pose y velocidad verdaderas para `telemetry.sim_truth`."""
        state = self.state
        return {
            "x": round(state.x, 6),
            "y": round(state.y, 6),
            "theta": round(state.theta, 6),
            "speed_mps": round(state.speed, 6),
            "distance_m": round(state.distance_m, 6),
        }

    def battery_v(self) -> float:
        return battery_voltage(self.params.battery_nominal_v, self.pwm_left, self.pwm_right)

    def _current_coverage(self) -> np.ndarray:
        pose = (self.state.x, self.state.y, self.state.theta)
        if pose != self._coverage_pose:
            points = sensor_positions(*pose, self.params)
            self._coverage = coverage(points, self.track, self.params)
            self._coverage_pose = pose
        return self._coverage
