"""Ritmo en tiempo real y cola de salida con descarte (research R11)."""

from __future__ import annotations

import pytest

from velocista_sim.server.pacer import OutboundQueue, Pacer


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class FakeSession:
    def __init__(self) -> None:
        self.steps = 0

    def step(self) -> list[dict]:
        self.steps += 1
        return [{"type": "telemetry", "seq": self.steps}]

    def next_telemetry_step(self) -> int:
        return self.steps + 1


def _pacer() -> tuple[Pacer, FakeClock, FakeSession, OutboundQueue]:
    clock, session, queue = FakeClock(), FakeSession(), OutboundQueue()
    pacer = Pacer(session, clock, queue)
    return pacer, clock, session, queue


def test_runs_due_steps() -> None:
    pacer, clock, session, _ = _pacer()
    assert pacer.tick() == 0
    clock.now += 0.0101
    assert pacer.tick() == 5
    clock.now += 0.004
    assert pacer.tick() == 2
    assert session.steps == 7


def test_batches_are_limited_and_lag_is_dropped() -> None:
    pacer, clock, session, _ = _pacer()
    clock.now += 1.0  # 500 pasos de atraso
    assert pacer.tick() == 50
    assert pacer.tick() == 0  # t_base se movió: no recupera a ráfagas
    clock.now += 0.02
    assert pacer.tick() == 10
    assert session.steps == 60


def test_small_lag_is_recovered() -> None:
    pacer, clock, session, _ = _pacer()
    clock.now += 0.15  # 75 pasos
    assert pacer.tick() == 50
    assert pacer.tick() == 25  # quedaban 25 pasos (50 ms ≤ 100 ms): se recuperan
    assert session.steps == 75


def test_queue_drops_telemetry_only() -> None:
    queue = OutboundQueue()
    for seq in range(30):
        assert queue.put({"type": "telemetry", "seq": seq})
    assert queue.telemetry_pending == 25
    for kind in ("hello", "config", "event", "error", "catalog"):
        assert queue.put({"type": kind})
    items = [queue.get_nowait() for _ in range(len(queue))]
    assert [m["seq"] for m in items if m["type"] == "telemetry"] == list(range(25))
    assert [m["type"] for m in items if m["type"] != "telemetry"] == ["hello", "config", "event", "error", "catalog"]
    assert queue.telemetry_pending == 0


def test_queue_overflow_asks_to_close() -> None:
    queue = OutboundQueue()
    for _ in range(1000):
        assert queue.put({"type": "event"})
    assert not queue.overflow
    assert not queue.put({"type": "error"})
    assert queue.overflow


def test_overflow_stops_pacer() -> None:
    pacer, clock, _, queue = _pacer()
    for _ in range(1001):
        queue.put({"type": "config"})
    clock.now += 0.01
    pacer.tick()
    assert pacer.should_close


@pytest.mark.parametrize("advance, expected", [(0.0, 0.002), (0.0015, 0.0005)])
def test_sleep_until_next_telemetry(advance: float, expected: float) -> None:
    pacer, clock, _, _ = _pacer()
    clock.now += advance
    assert pacer.sleep_time() == pytest.approx(expected)
