"""Núcleo `Session` sin E/S: apertura, corridas, comandos, determinismo (SC-001, SC-003, SC-005, SC-007).

Cada mensaje emitido pasa por `MessageChecker` (contrato + reglas de secuencia).
"""

from __future__ import annotations

import pytest

from support.contract_client import is_event
from support.session_driver import SessionDriver, events, of_type

LAP_LIMIT_STEPS = 9000  # 18 s simulados


def _start(driver: SessionDriver) -> dict:
    emitted = driver.command("start")
    started = events(emitted, "run_started")
    assert len(started) == 1
    return started[0]


def _without_session_id(messages: list[dict]) -> list[dict]:
    return [{k: v for k, v in m.items() if k != "session_id"} for m in messages]


# --- Apertura y telemetría sin corrida ------------------------------------------------------


def test_open_sends_hello_and_config() -> None:
    driver = SessionDriver()
    hello, config = driver.opening
    assert hello["type"] == "hello" and hello["t_ms"] == 0
    assert hello["source"] == "sim"
    assert hello["robot"]["id"] == "velocista-01"
    assert hello["session_id"].startswith("s-") and len(hello["session_id"]) == 10
    caps = hello["capabilities"]
    assert caps["line_sensors"] == 16 and caps["encoders"] is False and caps["imu"] is False
    assert caps["lap_timing"] is True and caps["battery"]["voltage_sense"] is True
    assert config == {
        "type": "config", "v": 1, "t_ms": 0, "controller": "pid",
        "params": {"kp": 0.045, "ki": 0, "kd": 0.9}, "base_speed": 180, "rate_hz": 50,
        "track_id": "oval-01",
    }


def test_session_ids_are_unique() -> None:
    assert SessionDriver().opening[0]["session_id"] != SessionDriver().opening[0]["session_id"]


def test_idle_telemetry_every_ten_steps() -> None:
    driver = SessionDriver()
    telemetry = of_type(driver.run(100), "telemetry")
    assert [m["t_ms"] for m in telemetry] == [20 * k for k in range(1, 11)]
    assert [m["seq"] for m in telemetry] == list(range(10))
    for message in telemetry:
        assert message["running"] is False
        assert "run_id" not in message and "lap" not in message and "odometry" not in message
        assert "battery_v" in message and "sim_truth" in message
        assert message["control"] == {"p": 0, "i": 0, "d": 0, "out": 0}
        assert message["motors"] == {"left": 0, "right": 0}
    assert telemetry[0]["sim_truth"]["x"] == pytest.approx(0.85, abs=1e-6)


# --- Corridas ------------------------------------------------------------------------------


def test_default_config_does_three_laps_sc001() -> None:
    driver = SessionDriver()
    started = _start(driver)
    laps: list[dict] = []
    emitted: list[dict] = []
    while len(laps) < 3:
        lap, chunk = driver.run_until(is_event("lap"), LAP_LIMIT_STEPS)
        emitted += chunk
        laps.append(lap)
    assert not events(emitted, "off_track")
    assert [lap["lap"] for lap in laps] == [1, 2, 3]
    for lap in laps:
        assert lap["run_id"] == started["run_id"]
        assert 3000 <= lap["lap_ms"] <= 3900
    running = of_type(emitted, "telemetry")
    assert all(m["running"] and m["run_id"] == started["run_id"] and "lap" in m for m in running)
    lap_block = of_type(driver.run(10), "telemetry")[-1]["lap"]
    assert lap_block["n"] == 3 and 0 <= lap_block["current_ms"] <= 40

    finished = events(driver.command("stop"), "run_finished")
    assert len(finished) == 1
    summary = finished[0]["summary"]
    assert summary["laps"] == 3 and summary["off_tracks"] == 0
    times = [lap["lap_ms"] for lap in laps]
    assert summary["best_lap_ms"] == min(times)
    assert summary["avg_lap_ms"] == round(sum(times) / 3)
    assert summary["track_id"] == "oval-01" and summary["config_changed"] is False
    assert summary["config"] == {"controller": "pid", "params": {"kp": 0.045, "ki": 0, "kd": 0.9},
                                 "base_speed": 180}
    after = of_type(driver.run(20), "telemetry")
    assert all(m["running"] is False and "run_id" not in m for m in after)


def test_kp_zero_goes_off_track_sc005() -> None:
    driver = SessionDriver()
    driver.command("set_config", params={"kp": 0})
    started = _start(driver)
    off, _ = driver.run_until(is_event("off_track"), 5000)
    assert off["reason"] == "line_lost" and off["run_id"] == started["run_id"]
    assert off["t_ms"] - started["t_ms"] < 10_000
    finished = driver.messages[driver.messages.index(off) + 1]
    assert finished["event"] == "run_finished"
    assert finished["summary"]["off_tracks"] == 1
    assert finished["summary"]["laps"] == 0
    assert finished["summary"]["best_lap_ms"] is None and finished["summary"]["avg_lap_ms"] is None
    later = driver.run(20)
    assert all(m["running"] is False for m in of_type(later, "telemetry"))
    assert driver.command("stop")[0]["code"] == "no_run"


def test_off_track_order_in_the_same_step() -> None:
    driver = SessionDriver()
    driver.command("set_config", params={"kp": 0, "kd": 0})
    _start(driver)
    for _ in range(5000):
        emitted = driver.run(1)
        if events(emitted, "off_track"):
            kinds = [(m["type"], m.get("event")) for m in emitted]
            assert kinds[:2] == [("event", "off_track"), ("event", "run_finished")]
            for message in emitted[2:]:
                assert message["type"] == "telemetry" and message["running"] is False
            return
    raise AssertionError("no hubo off_track")


def test_set_config_during_run() -> None:
    driver = SessionDriver()
    _start(driver)
    driver.run(100)
    emitted = driver.command("set_config", params={"kp": 0.05})
    config = of_type(emitted, "config")[0]
    assert config["params"] == {"kp": 0.05, "ki": 0, "kd": 0.9} and config["base_speed"] == 180
    emitted = driver.command("set_config", base_speed=170)
    assert of_type(emitted, "config")[0]["params"]["kp"] == 0.05
    driver.run(100)
    summary = events(driver.command("stop"), "run_finished")[0]["summary"]
    assert summary["config_changed"] is True
    assert summary["config"]["params"]["kp"] == 0.045 and summary["config"]["base_speed"] == 180


def test_set_config_without_run_does_not_mark_next_run() -> None:
    driver = SessionDriver()
    driver.command("set_config", params={"kd": 1.0}, base_speed=170)
    _start(driver)
    driver.run(50)
    summary = events(driver.command("stop"), "run_finished")[0]["summary"]
    assert summary["config_changed"] is False
    assert summary["config"]["params"]["kd"] == 1.0 and summary["config"]["base_speed"] == 170


def test_set_rate_changes_telemetry_period() -> None:
    driver = SessionDriver()
    driver.run(10)
    emitted = driver.command("set_rate", hz=20)
    assert of_type(emitted, "config")[0]["rate_hz"] == 20
    telemetry = of_type(driver.run(200), "telemetry")
    times = [m["t_ms"] for m in telemetry]
    assert all(b - a == 50 for a, b in zip(times, times[1:]))
    assert len(telemetry) == 8


def test_set_rate_does_not_change_the_simulation() -> None:
    a, b = SessionDriver(), SessionDriver()
    for driver in (a, b):
        _start(driver)
        driver.run(1000)
    a.command("set_rate", hz=20)
    b.run(1)
    for driver in (a, b):
        driver.run(2500)
    summary_a = events(a.command("stop"), "run_finished")[0]["summary"]
    summary_b = events(b.command("stop"), "run_finished")[0]["summary"]
    assert summary_a == summary_b
    truth_a = {m["t_ms"]: m["sim_truth"] for m in of_type(a.messages, "telemetry")}
    truth_b = {m["t_ms"]: m["sim_truth"] for m in of_type(b.messages, "telemetry")}
    common = set(truth_a) & set(truth_b)
    assert len(common) > 50
    assert all(truth_a[t] == truth_b[t] for t in common)


def test_list_returns_catalog() -> None:
    driver = SessionDriver()
    catalog = of_type(driver.command("list"), "catalog")[0]
    assert catalog["robots"] == ["velocista-01"]
    assert catalog["tracks"] == ["oval-01"]


def test_reset_without_run_returns_to_start() -> None:
    driver = SessionDriver()
    _start(driver)
    driver.run(500)
    driver.command("stop")
    driver.run(100)
    moved = of_type(driver.messages, "telemetry")[-1]["sim_truth"]
    assert moved["x"] != pytest.approx(0.85, abs=0.01)
    emitted = driver.command("reset")
    assert all(m["type"] == "telemetry" for m in emitted)
    truth = of_type(driver.run(30), "telemetry")[-1]["sim_truth"]
    assert truth["x"] == pytest.approx(0.85, abs=1e-6) and truth["y"] == pytest.approx(0.65, abs=1e-6)
    assert truth["speed_mps"] == 0 and truth["theta"] == pytest.approx(0, abs=1e-9)


def test_state_rules() -> None:
    driver = SessionDriver()
    emitted = driver.command("stop")
    assert [(m["code"], m["cmd"]) for m in of_type(emitted, "error")] == [("no_run", "stop")]
    assert not events(emitted)
    _start(driver)
    emitted = driver.command("start")
    assert [(m["code"], m["cmd"]) for m in of_type(emitted, "error")] == [("run_active", "start")]
    emitted = driver.command("reset")
    assert [(m["code"], m["cmd"]) for m in of_type(emitted, "error")] == [("run_active", "reset")]


def test_base_speed_zero_never_ends_alone() -> None:
    driver = SessionDriver()
    driver.command("set_config", base_speed=0)
    _start(driver)
    emitted = driver.run(2500)  # 5 s
    assert not events(emitted)
    assert all(m["running"] for m in of_type(emitted, "telemetry"))


def test_invalid_frames_answer_error_and_keep_going() -> None:
    driver = SessionDriver()
    for frame, code in [("no json", "invalid_json"), ('{"cmd": "go"}', "unknown_cmd"),
                        ('{"cmd": "start", "v": 2}', "unsupported_version"),
                        ('{"cmd": "set_rate", "hz": 150}', "out_of_range"),
                        ('{"cmd": "set_config"}', "invalid_params")]:
        driver.send_raw(frame)
        errors = of_type(driver.run(1), "error")
        assert [e["code"] for e in errors] == [code]
    assert of_type(driver.run(20), "telemetry")


def test_commands_in_one_step_are_applied_in_order() -> None:
    driver = SessionDriver()
    driver.send("set_rate", hz=10)
    driver.send("list")
    driver.send("set_config", base_speed=100)
    emitted = driver.run(1)
    assert [m["type"] for m in emitted] == ["config", "catalog", "config"]
    assert all(m["t_ms"] == 0 for m in emitted)


# --- Reproducibilidad (SC-003) y rechazos sin efecto (SC-007) -------------------------------


def _scripted_runs(driver: SessionDriver, idle: int = 0) -> None:
    driver.run(idle)
    for _ in range(2):
        _start(driver)
        driver.run(2000)
        driver.command("stop")
        driver.run(25)


def test_same_seed_same_commands_same_messages_sc003() -> None:
    a, b = SessionDriver(seed=5), SessionDriver(seed=5)
    _scripted_runs(a)
    _scripted_runs(b)
    assert _without_session_id(a.messages) == _without_session_id(b.messages)


def test_each_run_has_its_own_noise_sc003() -> None:
    driver = SessionDriver()
    _scripted_runs(driver)
    starts = events(driver.messages, "run_started")
    telemetry = of_type(driver.messages, "telemetry")

    def sensors_after(start: dict) -> list[list[int]]:
        return [m["sensors"] for m in telemetry if m.get("run_id") == start["run_id"]][:20]

    assert sensors_after(starts[0]) != sensors_after(starts[1])


def test_run_does_not_depend_on_idle_time_sc003() -> None:
    a, b = SessionDriver(), SessionDriver()
    _scripted_runs(a, idle=0)
    _scripted_runs(b, idle=37)
    summaries_a = [m["summary"] for m in events(a.messages, "run_finished")]
    summaries_b = [m["summary"] for m in events(b.messages, "run_finished")]
    assert summaries_a == summaries_b


def test_different_seed_changes_noise() -> None:
    a, b = SessionDriver(seed=1), SessionDriver(seed=2)
    for driver in (a, b):
        _start(driver)
        driver.run(100)
    sensors_a = [m["sensors"] for m in of_type(a.messages, "telemetry")]
    sensors_b = [m["sensors"] for m in of_type(b.messages, "telemetry")]
    assert sensors_a != sensors_b


REJECTED_IDLE = ["{", '{"cmd": "volar"}', '{"cmd": "list", "v": 3}', '{"cmd": "set_rate", "hz": 5}',
                 '{"cmd": "set_config", "base_speed": 300}', '{"cmd": "set_config", "params": {}}',
                 '{"cmd": "stop"}']
REJECTED_RUNNING = ['{"cmd": "start"}', '{"cmd": "reset"}', '{"cmd": "set_rate", "hz": 101}',
                    '{"cmd": "set_config", "params": {"kd": -1}}']


def test_rejections_have_no_effect_sc007() -> None:
    a, b = SessionDriver(), SessionDriver()
    a.run(15)
    for frame in REJECTED_IDLE:
        a.send_raw(frame)
    a.run(1)
    b.run(16)
    for driver in (a, b):
        _start(driver)
        driver.run(700)
    for frame in REJECTED_RUNNING:
        a.send_raw(frame)
    a.run(1)
    b.run(1)
    for driver in (a, b):
        driver.run(700)
        driver.command("stop")
    errors = of_type(a.messages, "error")
    assert len(errors) == len(REJECTED_IDLE) + len(REJECTED_RUNNING)
    assert not of_type(b.messages, "error")
    others_a = [m for m in _without_session_id(a.messages) if m["type"] != "error"]
    assert others_a == _without_session_id(b.messages)
