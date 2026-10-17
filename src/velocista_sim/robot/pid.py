"""PID discreto por tick de control, sin dividir por el periodo (research R7)."""

from __future__ import annotations

TERM_LIMIT = 1e9


def _bound(value: float) -> float:
    """Acota a ±1e9 para que la telemetría nunca lleve números no finitos."""
    return min(max(value, -TERM_LIMIT), TERM_LIMIT)


class Pid:
    """`p = kp·e`, `i = ki·Σe`, `d = kd·(e − e_prev)`; sin patada derivativa tras reiniciar."""

    def __init__(self) -> None:
        self.integral = 0.0
        self.prev_error: int | None = None

    def reset(self) -> None:
        self.integral = 0.0
        self.prev_error = None

    def step(self, error: int, kp: float, ki: float, kd: float) -> tuple[float, float, float, float]:
        """Un tick: devuelve (`p`, `i`, `d`, `out`)."""
        self.integral = _bound(self.integral + error)
        previous = error if self.prev_error is None else self.prev_error
        self.prev_error = error
        p = _bound(kp * error)
        i = _bound(ki * self.integral)
        d = _bound(kd * (error - previous))
        return p, i, d, _bound(p + i + d)
