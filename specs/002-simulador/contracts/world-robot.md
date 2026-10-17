# Interfaz interna: mundo ↔ robot ↔ sesión

Frontera que materializa el principio III. Solo `velocista_sim.server.session` importa ambos
paquetes. Firmas orientativas (los nombres son los que se implementan; los cuerpos, no).

## `velocista_sim.world`

```python
@dataclass(frozen=True)
class WorldParams:
    line_sensors: int; sensor_pitch_m: float; sensor_offset_m: float
    adc_bits: int; adc_white: int; adc_black: int; adc_noise: int
    max_speed_mps: float; motor_tau_ms: float; wheelbase_m: float
    max_lateral_accel_mps2: float; battery_nominal_v: float

class TrackGeometry:
    @classmethod
    def from_track(cls, track: dict) -> "TrackGeometry": ...   # track v1 ya validada

@dataclass(frozen=True)
class LapCompleted: lap: int; lap_ms: int
@dataclass(frozen=True)
class OffTrack: reason: str = "line_lost"

class World:
    DT_S: ClassVar[float] = 0.002
    def __init__(self, params: WorldParams, track: TrackGeometry) -> None: ...
    def reset_to_start(self) -> None: ...              # pose en start.at, ruedas 0, contadores 0
    def set_params(self, params: WorldParams) -> None: ...
    def set_motor_pwm(self, left: int, right: int) -> None: ...
    def read_sensors(self, rng: numpy.random.Generator) -> list[int]: ...
    def step(self) -> None: ...                        # un paso de física de DT_S
    def begin_run(self, t_ms: int) -> None: ...        # arranca progreso, vueltas y detección
    def detect(self, t_ms: int) -> list[LapCompleted | OffTrack]: ...
    def truth(self) -> dict: ...                       # {x, y, theta, speed_mps, distance_m}
    def battery_v(self) -> float: ...
```

## `velocista_sim.robot`

```python
@dataclass(frozen=True)
class RobotParams:
    line_sensors: int; adc_white: int; adc_black: int; control_period_ms: float

@dataclass(frozen=True)
class PidConfig:
    kp: float; ki: float; kd: float; base_speed: int

@dataclass(frozen=True)
class ControlOutput:
    line_position: int; line_lost: bool; error: int
    p: float; i: float; d: float; out: float
    left: int; right: int

class Robot:
    def __init__(self, params: RobotParams, config: PidConfig) -> None: ...
    def reset(self) -> None: ...                       # integral, error previo, última posición
    def set_config(self, config: PidConfig) -> None: ...
    def set_params(self, params: RobotParams) -> None: ...
    def tick(self, sensors: Sequence[int], running: bool) -> ControlOutput: ...
```

## Reglas

- `robot` no importa `velocista_sim.world` ni `velocista_sim.server`; `world` no importa
  `velocista_sim.robot` ni `velocista_sim.server`. Ninguno importa `time`, `datetime`,
  `random` ni `asyncio` (`tests/unit/test_architecture.py`).
- Lo único que cruza de `world` a `robot` es `list[int]` (lecturas ADC). Lo único que cruza de
  `robot` a `world` es `(left, right)` en PWM.
- `World.truth()` solo lo usa la sesión para `telemetry.sim_truth`.
- Toda aleatoriedad entra por el `rng` que pasa la sesión.
