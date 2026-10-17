"""Geometría de una pista track v1 precalculada para la simulación (research R3, R9)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

CELL_M = 0.05
PROJECT_WINDOW = 25  # tramos a cada lado de la última proyección (≈ 0,125 m ≫ 6 mm por paso)


@dataclass(frozen=True, eq=False)
class TrackGeometry:
    """Pista ya validada: línea central, tramos con tinta y grilla espacial. Inmutable."""

    track_id: str
    points: np.ndarray  # (P, 2) centerline
    seg_a: np.ndarray  # (S, 2) inicio de cada tramo de la centerline (incluye el cierre)
    seg_b: np.ndarray  # (S, 2) fin de cada tramo
    seg_len: np.ndarray  # (S,)
    cum_s: np.ndarray  # (S,) longitud acumulada al inicio de cada tramo
    length: float
    closed: bool
    ink_a: np.ndarray  # (M, 2) tramos con tinta (centerline menos gaps)
    ink_b: np.ndarray
    grid: dict[tuple[int, int], np.ndarray]
    board: tuple[float, float]
    line_width: float
    start_s: float

    @classmethod
    def from_track(cls, track: dict) -> "TrackGeometry":
        """Precalcula la geometría de una pista track v1 (que ya pasó `validate_track`)."""
        points = np.asarray(track["centerline"], dtype=float)
        closed = bool(track["closed"])
        seg_a = points if closed else points[:-1]
        seg_b = np.roll(points, -1, axis=0) if closed else points[1:]
        seg_len = np.hypot(*(seg_b - seg_a).T)
        total = np.cumsum(seg_len)
        cum_s = np.concatenate(([0.0], total[:-1]))
        length = float(total[-1])

        intervals = _gap_intervals(track["gaps"], length, closed)
        ink_a, ink_b = _ink_segments(seg_a, seg_b, seg_len, cum_s, intervals)
        board = (float(track["board"]["width"]), float(track["board"]["height"]))
        return cls(
            track_id=track["id"], points=points, seg_a=seg_a, seg_b=seg_b, seg_len=seg_len,
            cum_s=cum_s, length=length, closed=closed, ink_a=ink_a, ink_b=ink_b,
            grid=_build_grid(ink_a, ink_b), board=board, line_width=float(track["line_width"]),
            start_s=float(track["start"]["at"]),
        )

    def pose_at(self, s: float) -> tuple[float, float, float]:
        """Punto y rumbo (rad) a la distancia `s` a lo largo de la línea central."""
        s = s % self.length if self.closed else min(max(s, 0.0), self.length)
        index = int(np.searchsorted(self.cum_s, s, side="right")) - 1
        index = min(max(index, 0), len(self.seg_len) - 1)
        a, b = self.seg_a[index], self.seg_b[index]
        t = (s - self.cum_s[index]) / self.seg_len[index] if self.seg_len[index] > 0 else 0.0
        x, y = a + (b - a) * t
        heading = math.atan2(b[1] - a[1], b[0] - a[0])
        return float(x), float(y), heading

    def project(self, x: float, y: float, hint: int | None = None) -> tuple[float, int]:
        """Proyección de (x, y) sobre la línea central: (`s`, índice de tramo).

        Con `hint` busca solo en una ventana de tramos alrededor de él; sin `hint`, en todos.
        """
        count = len(self.seg_len)
        if hint is None or count <= 2 * PROJECT_WINDOW + 1:
            indices = np.arange(count)
        elif self.closed:
            indices = (np.arange(hint - PROJECT_WINDOW, hint + PROJECT_WINDOW + 1)) % count
        else:
            indices = np.arange(max(hint - PROJECT_WINDOW, 0), min(hint + PROJECT_WINDOW + 1, count))
        a, b = self.seg_a[indices], self.seg_b[indices]
        ab = b - a
        lengths2 = (ab * ab).sum(axis=1)
        ap = np.array([x, y]) - a
        t = np.clip((ap * ab).sum(axis=1) / np.where(lengths2 > 0, lengths2, 1.0), 0.0, 1.0)
        diff = ap - ab * t[:, None]
        best = int(np.argmin((diff * diff).sum(axis=1)))
        index = int(indices[best])
        s = float(self.cum_s[index] + t[best] * self.seg_len[index])
        if self.closed and s >= self.length:
            s -= self.length
        return s, index

    def ink_candidates(self, bbox: tuple[float, float, float, float]) -> np.ndarray:
        """Índices de los tramos con tinta registrados en las celdas que toca `bbox`.

        Puede haber repetidos (un tramo en dos celdas); no afecta a la distancia mínima.
        """
        x0, y0, x1, y1 = bbox
        i0, i1 = math.floor(x0 / CELL_M), math.floor(x1 / CELL_M)
        j0, j1 = math.floor(y0 / CELL_M), math.floor(y1 / CELL_M)
        found = [
            cell
            for i in range(i0, i1 + 1)
            for j in range(j0, j1 + 1)
            if (cell := self.grid.get((i, j))) is not None
        ]
        if not found:
            return np.empty(0, dtype=np.intp)
        return found[0] if len(found) == 1 else np.concatenate(found)


def _gap_intervals(gaps: list[dict], length: float, closed: bool) -> list[tuple[float, float]]:
    """Intervalos `[inicio, fin)` sin tinta; en pistas cerradas un corte puede pasar por 0."""
    intervals: list[tuple[float, float]] = []
    for gap in gaps:
        start, end = float(gap["at"]), float(gap["at"]) + float(gap["length"])
        if closed and end > length:
            intervals.append((start, length))
            intervals.append((0.0, end - length))
        else:
            intervals.append((start, end))
    return sorted(intervals)


def _ink_segments(seg_a, seg_b, seg_len, cum_s, intervals) -> tuple[np.ndarray, np.ndarray]:
    """Corta cada tramo de la centerline quitando los intervalos de los cortes."""
    if not intervals:
        return seg_a.copy(), seg_b.copy()
    starts: list[np.ndarray] = []
    ends: list[np.ndarray] = []
    for a, b, seg_length, s0 in zip(seg_a, seg_b, seg_len, cum_s):
        if seg_length <= 0:
            continue
        s1 = s0 + seg_length
        pieces = [(s0, s1)]
        for g0, g1 in intervals:
            if g1 <= s0 or g0 >= s1:
                continue
            pieces = [p for lo, hi in pieces for p in ((lo, min(hi, g0)), (max(lo, g1), hi)) if p[1] > p[0]]
        for lo, hi in pieces:
            starts.append(a + (b - a) * ((lo - s0) / seg_length))
            ends.append(a + (b - a) * ((hi - s0) / seg_length))
    if not starts:
        return np.empty((0, 2)), np.empty((0, 2))
    return np.array(starts), np.array(ends)


def _build_grid(ink_a: np.ndarray, ink_b: np.ndarray) -> dict[tuple[int, int], np.ndarray]:
    """Celdas de `CELL_M` → índices de los tramos con tinta cuya caja toca la celda."""
    cells: dict[tuple[int, int], list[int]] = {}
    for index, (a, b) in enumerate(zip(ink_a, ink_b)):
        i0, i1 = sorted((math.floor(a[0] / CELL_M), math.floor(b[0] / CELL_M)))
        j0, j1 = sorted((math.floor(a[1] / CELL_M), math.floor(b[1] / CELL_M)))
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                cells.setdefault((i, j), []).append(index)
    return {cell: np.array(indices, dtype=np.intp) for cell, indices in cells.items()}
