"""Robot a bordo: posición de línea y PID. No conoce el mundo ni el servidor."""

from .params import ControlOutput, PidConfig, RobotParams
from .robot import Robot

__all__ = ["ControlOutput", "PidConfig", "Robot", "RobotParams"]
