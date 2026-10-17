"""Lecturas ADC de la regleta de sensores (FR-012, research R3).

La cobertura de cada sensor es una rampa lineal con la distancia a la tinta, con apertura
`a = sensor_pitch_m`: `cov = clip((line_width/2 + a/2 − d) / a, 0, 1)`.
"""

from __future__ import annotations

import math

import numpy as np

from .params import WorldParams
from .track import TrackGeometry


def sensor_positions(x: float, y: float, theta: float, params: WorldParams) -> np.ndarray:
    """Posiciones (N, 2) de los sensores: índice 0 a la izquierda, regleta delante del eje."""
    count = params.line_sensors
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    lateral = ((count - 1) / 2 - np.arange(count)) * params.sensor_pitch_m  # + = izquierda
    cx = x + params.sensor_offset_m * cos_t
    cy = y + params.sensor_offset_m * sin_t
    return np.column_stack((cx - lateral * sin_t, cy + lateral * cos_t))


def coverage(points: np.ndarray, track: TrackGeometry, params: WorldParams) -> np.ndarray:
    """Fracción (0 … 1) de tinta que ve cada sensor en `points`, sin ruido."""
    aperture = params.sensor_pitch_m
    reach = track.line_width / 2 + aperture / 2
    x0, y0 = points.min(axis=0) - reach
    x1, y1 = points.max(axis=0) + reach
    candidates = track.ink_candidates((x0, y0, x1, y1))
    if len(candidates) == 0:
        return np.zeros(len(points))
    a = track.ink_a[candidates]
    ab = track.ink_b[candidates] - a
    lengths2 = (ab * ab).sum(axis=1)
    lengths2 = np.where(lengths2 > 0, lengths2, 1.0)
    ap = points[:, None, :] - a[None, :, :]
    t = np.einsum("nkc,kc->nk", ap, ab) / lengths2
    np.clip(t, 0.0, 1.0, out=t)
    diff = ap - t[..., None] * ab
    distance = np.sqrt(np.einsum("nkc,nkc->nk", diff, diff).min(axis=1))
    return np.clip((reach - distance) / aperture, 0.0, 1.0)


def readings(cov: np.ndarray, params: WorldParams, rng: np.random.Generator) -> list[int]:
    """Lecturas ADC enteras: `round(blanco + (negro − blanco)·cov + ruido)`, recortadas al rango."""
    values = params.adc_white + (params.adc_black - params.adc_white) * cov
    if params.adc_noise > 0:
        values = values + rng.integers(-params.adc_noise, params.adc_noise + 1, size=len(cov))
    top = 2**params.adc_bits - 1
    return [int(v) for v in np.clip(np.rint(values), 0, top)]
