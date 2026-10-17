"""Mundo simulado: pista, física y regleta de sensores. No conoce al robot ni al servidor."""

from .params import WorldParams
from .track import TrackGeometry
from .world import LapCompleted, OffTrack, World

__all__ = ["LapCompleted", "OffTrack", "TrackGeometry", "World", "WorldParams"]
