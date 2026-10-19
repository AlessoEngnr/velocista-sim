"""Prueba de humo del panel con Playwright (specs/003-panel-laboratorio, research R12).

Contra un uvicorn real: el panel abre su sesión, muestra `hello`/`config`, controla una corrida
(Iniciar → EN CORRIDA → Detener → resumen → Reiniciar), ajusta el controlador (`set_config`,
`set_rate`, envío limitado al arrastrar), cambia de robot y de pista, carga pistas desde archivo
y todo frame cumple el contrato. Con un servidor falso (`route_web_socket`): errores en el
registro, controles que vuelven al `config` ante un rechazo, vueltas objetivo, `unknown_track` de
la conexión, desconexión y reconexión.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from playwright.sync_api import Page, expect

from support.browser import Capture, assert_frames_valid
from support.fake_server import SIM_CONFIG, SIM_HELLO, FakeServer, event, open_session, telemetry


def _by_id(page: Page, test_id: str):
    return page.get_by_test_id(test_id)


def _wait_for(condition: Callable[[], bool], page: Page, timeout_ms: int = 5000) -> None:
    """Reintenta `condition` mientras la página procesa eventos (los frames llegan por callbacks)."""
    for _ in range(timeout_ms // 50):
        if condition():
            return
        page.wait_for_timeout(50)
    assert condition(), "la condición no se cumplió a tiempo"


REPO_ROOT = Path(__file__).resolve().parents[2]
OVAL_01 = REPO_ROOT / "config" / "tracks" / "oval-01.json"
GAPS_OVERLAP = REPO_ROOT / "contract" / "examples" / "invalid" / "track" / "gaps-overlap.json"
STOP_TO_CHANGE = "Detené la corrida para cambiar esto"


def _seq(page: Page) -> int:
    return int(_by_id(page, "seq").text_content())


def _trail_points(page: Page) -> int:
    return int(_by_id(page, "trail-canvas").get_attribute("data-points"))


# --- Servidor real ---------------------------------------------------------------------------


def test_panel_connects_and_shows_the_session(page: Page, capture: Capture, live_url: str) -> None:
    page.goto(live_url)

    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    expect(_by_id(page, "conn-status")).to_have_text("● CONECTADO")
    expect(_by_id(page, "robot-id")).to_have_text("velocista-01")
    expect(_by_id(page, "source")).to_have_text("sim")
    expect(_by_id(page, "rate-hz")).to_have_text("50 Hz")
    expect(_by_id(page, "track-id")).to_have_text("oval-01")
    expect(_by_id(page, "run-status")).to_have_attribute("data-state", "idle")
    expect(_by_id(page, "btn-reconnect")).to_be_hidden()
    expect(_by_id(page, "btn-start")).to_be_enabled()

    # Tras el primer `config` el panel pide el catálogo, y el servidor lo responde.
    _wait_for(lambda: any(m.get("type") == "catalog" for m in capture.received()), page)
    assert capture.sent() == [{"cmd": "list"}]
    assert capture.sockets and capture.sockets[0].endswith("/ws")

    assert_frames_valid(capture.frames)
    assert capture.console_errors == []


def test_run_start_stop_and_reset(page: Page, capture: Capture, live_url: str) -> None:
    page.goto(live_url)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    expect(_by_id(page, "robot-id")).to_have_text("velocista-01")
    expect(_by_id(page, "run-status")).to_have_attribute("data-state", "idle")
    expect(_by_id(page, "btn-stop")).to_be_disabled()

    _by_id(page, "btn-start").click()
    expect(_by_id(page, "run-status")).to_have_attribute("data-state", "running")
    expect(_by_id(page, "run-status")).to_have_text("● EN CORRIDA")
    expect(_by_id(page, "run-id")).not_to_have_text("—")
    expect(_by_id(page, "btn-start")).to_be_disabled()

    first = _seq(page)
    _wait_for(lambda: _seq(page) > first, page)
    _wait_for(lambda: _trail_points(page) > 0, page)
    expect(_by_id(page, "pid-out")).not_to_have_text("—")
    expect(_by_id(page, "pwm-left")).to_contain_text("PWM")

    _by_id(page, "btn-stop").click()
    expect(_by_id(page, "summaries").locator("li")).to_have_count(1)
    expect(_by_id(page, "run-status")).to_have_attribute("data-state", "idle")

    _by_id(page, "btn-reset").click()
    _wait_for(lambda: {"cmd": "reset"} in capture.sent(), page)
    expect(_by_id(page, "trail-canvas")).to_have_attribute("data-points", "0")

    assert_frames_valid(capture.frames)
    assert capture.console_errors == []


def _set_configs(capture: Capture) -> list[dict]:
    return [command for command in capture.sent() if command["cmd"] == "set_config"]


def _commit(page: Page, test_id: str, text: str) -> None:
    """Escribe en un campo numérico y lo confirma con Enter (dispara `change`)."""
    field = _by_id(page, test_id)
    field.fill(text)
    field.press("Enter")


# Arrastre del slider de `kp`: 50 eventos `input` con valores crecientes durante 1 s, entre
# `pointerdown` y `pointerup` + `change`, como lo haría el mouse.
DRAG_KP = """
async (slider) => {
  slider.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
  for (let i = 1; i <= 50; i++) {
    slider.value = String(i * 0.0005);
    slider.dispatchEvent(new Event("input", { bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  slider.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));
  slider.dispatchEvent(new Event("change", { bubbles: true }));
  return slider.value;
}
"""


def test_tuning_sends_set_config_and_set_rate(page: Page, capture: Capture, live_url: str) -> None:
    page.goto(live_url)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    expect(_by_id(page, "kp-input")).to_have_value("0.0450")

    # Campo numérico: envía el valor exacto al confirmar y muestra el `config` de respuesta.
    _commit(page, "kp-input", "0.05")
    _wait_for(lambda: {"cmd": "set_config", "params": {"kp": 0.05}} in capture.sent(), page)
    expect(_by_id(page, "kp-input")).to_have_value("0.0500")
    expect(_by_id(page, "kp-input")).to_have_attribute("aria-invalid", "false")

    # Coma decimal: se envía como número JSON 0.06, no como el texto "0,06".
    _commit(page, "kp-input", "0,06")
    _wait_for(lambda: {"cmd": "set_config", "params": {"kp": 0.06}} in capture.sent(), page)
    comma = _set_configs(capture)[-1]["params"]["kp"]
    assert type(comma) is float and comma == 0.06
    raw = [f.payload for f in capture.frames if f.direction == "sent" and '"set_config"' in f.payload][-1]
    assert '"kp":0.06' in raw.replace(" ", ""), raw
    expect(_by_id(page, "kp-input")).to_have_value("0.0600")

    # Arrastre continuo: pocos envíos por segundo y siempre el valor final.
    before = len(_set_configs(capture))
    final = _by_id(page, "kp-range").evaluate(DRAG_KP)
    assert float(final) == 0.025
    _wait_for(lambda: _set_configs(capture)[-1] == {"cmd": "set_config", "params": {"kp": 0.025}}, page)
    expect(_by_id(page, "kp-input")).to_have_value("0.0250")
    page.wait_for_timeout(400)
    dragged = _set_configs(capture)[before:]
    assert 1 <= len(dragged) <= 7, f"{len(dragged)} set_config durante el arrastre"
    assert dragged[-1] == {"cmd": "set_config", "params": {"kp": 0.025}}

    # Valores inválidos: se marcan y no se envía nada.
    sent = len(capture.sent())
    _commit(page, "kp-input", "-1")
    expect(_by_id(page, "kp-input")).to_have_attribute("aria-invalid", "true")
    _commit(page, "rate-input", "150")
    expect(_by_id(page, "rate-input")).to_have_attribute("aria-invalid", "true")
    page.wait_for_timeout(200)
    assert len(capture.sent()) == sent

    # Frecuencia válida: `set_rate` y la barra superior muestra la confirmada.
    _commit(page, "rate-input", "100")
    _wait_for(lambda: {"cmd": "set_rate", "hz": 100} in capture.sent(), page)
    expect(_by_id(page, "rate-hz")).to_have_text("100 Hz")
    expect(_by_id(page, "rate-input")).to_have_value("100")
    expect(_by_id(page, "rate-input")).to_have_attribute("aria-invalid", "false")

    assert_frames_valid(capture.frames)
    assert capture.console_errors == []


def test_tuning_during_a_run_marks_config_changed(page: Page, capture: Capture, live_url: str) -> None:
    page.goto(live_url)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    expect(_by_id(page, "kp-input")).to_have_value("0.0450")

    _by_id(page, "btn-start").click()
    expect(_by_id(page, "run-status")).to_have_attribute("data-state", "running")
    _commit(page, "kp-input", "0.04")
    expect(_by_id(page, "kp-input")).to_have_value("0.0400")
    _by_id(page, "btn-stop").click()

    latest = _by_id(page, "summaries").locator("li").first
    changed = latest.locator("div", has=page.locator("dt", has_text="CAMBIÓ CONFIG")).locator("dd")
    expect(changed).to_have_text("sí")
    assert_frames_valid(capture.frames)
    assert capture.console_errors == []


def _received_hellos(capture: Capture) -> list[dict]:
    return [message for message in capture.received() if message.get("type") == "hello"]


def _open_robot_track_tab(page: Page) -> None:
    _by_id(page, "tab-robot-track").click()
    expect(_by_id(page, "robot-select")).to_be_visible()


def test_robot_and_track_selection(page: Page, capture: Capture, live_url: str, tmp_path: Path) -> None:
    page.goto(live_url)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    _wait_for(lambda: any(m.get("type") == "catalog" for m in capture.received()), page)
    _open_robot_track_tab(page)

    # Catálogo con el robot y la pista vigentes marcados.
    robot_option = _by_id(page, "robot-select").locator('option[value="velocista-01"]')
    track_option = _by_id(page, "track-select").locator('option[value="oval-01"]')
    expect(robot_option).to_have_attribute("data-current", "true")
    expect(robot_option).to_contain_text("vigente")
    expect(track_option).to_have_attribute("data-current", "true")

    # Con una corrida activa todo queda deshabilitado, con el aviso.
    _by_id(page, "btn-start").click()
    expect(_by_id(page, "run-status")).to_have_attribute("data-state", "running")
    for test_id in ("robot-select", "track-select", "track-file", "btn-catalog-refresh"):
        expect(_by_id(page, test_id)).to_be_disabled()
    expect(page.locator('[data-role="robot-track-hint"]')).to_be_visible()
    expect(page.locator('[data-role="robot-track-hint"]')).to_have_text(STOP_TO_CHANGE)
    _wait_for(lambda: _trail_points(page) > 0, page)
    _by_id(page, "btn-stop").click()
    expect(_by_id(page, "run-status")).to_have_attribute("data-state", "idle")
    expect(_by_id(page, "robot-select")).to_be_enabled()
    expect(page.locator('[data-role="robot-track-hint"]')).to_be_hidden()
    assert _trail_points(page) > 0

    # Elegir robot: `load`, nuevo `hello` + `config` y rastro limpio.
    _by_id(page, "robot-select").select_option("velocista-01")
    _wait_for(lambda: {"cmd": "load", "robot_id": "velocista-01"} in capture.sent(), page)
    _wait_for(lambda: len(_received_hellos(capture)) == 2, page)
    expect(_by_id(page, "trail-canvas")).to_have_attribute("data-points", "0")
    expect(_by_id(page, "robot-id")).to_have_text("velocista-01")
    expect(_by_id(page, "kp-input")).to_be_enabled()

    # Archivo de pista válido: `load_track` con su contenido.
    _by_id(page, "track-file").set_input_files(str(OVAL_01))
    _wait_for(lambda: any(c["cmd"] == "load_track" for c in capture.sent()), page)
    expect(_by_id(page, "track-id")).to_have_text("oval-01")

    # Archivo que no es JSON: error local y nada enviado.
    sent = len(capture.sent())
    not_json = tmp_path / "pista.txt"
    not_json.write_text("esto no es una pista", encoding="utf-8")
    _by_id(page, "track-file").set_input_files(str(not_json))
    expect(_by_id(page, "log").locator('li[data-kind="local"]').first).to_contain_text("El archivo no es JSON válido")
    page.wait_for_timeout(200)
    assert len(capture.sent()) == sent

    # JSON que no cumple track v1: `invalid_track` y la pista no cambia.
    invalid = tmp_path / "gaps-overlap.json"
    invalid.write_text(json.dumps(json.loads(GAPS_OVERLAP.read_text(encoding="utf-8"))["message"]), encoding="utf-8")
    _by_id(page, "track-file").set_input_files(str(invalid))
    expect(_by_id(page, "log").locator('li[data-kind="error"]').first).to_contain_text("invalid_track")
    expect(_by_id(page, "track-id")).to_have_text("oval-01")

    # Elegir pista y cancelar el aviso: no se reconecta.
    page.once("dialog", lambda dialog: dialog.dismiss())
    _by_id(page, "track-select").select_option("oval-01")
    page.wait_for_timeout(300)
    assert len(capture.sockets) == 1

    # Elegir pista y aceptar: sesión nueva con `track` y `robot` en la URL.
    page.once("dialog", lambda dialog: dialog.accept())
    _by_id(page, "track-select").select_option("oval-01")
    _wait_for(lambda: len(capture.sockets) == 2, page)
    assert "track=oval-01" in capture.sockets[1] and "robot=velocista-01" in capture.sockets[1]
    _wait_for(lambda: len(_received_hellos(capture)) == 3, page)
    hellos = _received_hellos(capture)
    assert hellos[2]["session_id"] != hellos[0]["session_id"]
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    expect(_by_id(page, "track-id")).to_have_text("oval-01")

    # El `load_track` con la pista inválida no cumple el contrato a propósito: el panel envía el
    # archivo tal cual y el servidor lo rechaza. Todo lo demás se valida.
    assert_frames_valid([f for f in capture.frames if '"straight-open"' not in f.payload])
    assert capture.console_errors == []


def test_file_track_is_marked_and_cannot_be_reopened(page: Page, capture: Capture, live_url: str, tmp_path: Path) -> None:
    """Una pista cargada por archivo solo existe en esta sesión: aparece como «(archivo)» y deshabilitada."""
    track = json.loads(OVAL_01.read_text(encoding="utf-8"))
    track["id"] = "oval-copia"
    copy = tmp_path / "oval-copia.json"
    copy.write_text(json.dumps(track), encoding="utf-8")

    page.goto(live_url)
    _wait_for(lambda: any(m.get("type") == "catalog" for m in capture.received()), page)
    _open_robot_track_tab(page)
    _by_id(page, "track-file").set_input_files(str(copy))
    expect(_by_id(page, "track-id")).to_have_text("oval-copia")

    _by_id(page, "btn-catalog-refresh").click()
    _wait_for(lambda: sum(m.get("type") == "catalog" for m in capture.received()) == 2, page)
    option = _by_id(page, "track-select").locator('option[value="oval-copia"]')
    expect(option).to_contain_text("(archivo)")
    expect(option).to_be_disabled()
    expect(option).to_have_attribute("data-current", "true")
    expect(_by_id(page, "track-select").locator('option[value="oval-01"]')).to_be_enabled()
    assert_frames_valid(capture.frames)
    assert capture.console_errors == []


# --- Servidor falso --------------------------------------------------------------------------


def test_rejected_tuning_returns_to_the_confirmed_config(page: Page, capture: Capture, live_url: str) -> None:
    """Ante un `error` de `set_config`/`set_rate`, los controles vuelven al último `config` (FR-013)."""
    server = FakeServer(page, open_session(SIM_HELLO, SIM_CONFIG))
    page.goto(live_url)
    expect(_by_id(page, "base-speed-input")).to_have_value("180")

    _commit(page, "base-speed-input", "200")
    _wait_for(lambda: server.commands("set_config") == [{"cmd": "set_config", "base_speed": 200}], page)
    expect(_by_id(page, "base-speed-range")).to_have_value("200")
    server.last.send({"type": "error", "v": 1, "t_ms": 2000, "code": "out_of_range", "cmd": "set_config",
                      "message": "base_speed fuera de rango"})
    expect(_by_id(page, "base-speed-input")).to_have_value("180")
    expect(_by_id(page, "base-speed-range")).to_have_value("180")
    expect(_by_id(page, "log").locator('li[data-kind="error"]')).to_have_count(1)

    _commit(page, "rate-input", "20")
    _wait_for(lambda: server.commands("set_rate") == [{"cmd": "set_rate", "hz": 20}], page)
    server.last.send({"type": "error", "v": 1, "t_ms": 2500, "code": "out_of_range", "cmd": "set_rate",
                      "message": "hz fuera de rango"})
    expect(_by_id(page, "rate-input")).to_have_value("50")
    expect(_by_id(page, "log").locator('li[data-kind="error"]')).to_have_count(2)
    # Los envíos de ajuste no se anotan en el registro; solo sus errores.
    expect(_by_id(page, "log").locator('li[data-kind="local"]')).to_have_count(0)
    assert capture.console_errors == []


def test_rejected_set_config_and_set_rate_appear_in_the_log(page: Page, capture: Capture, live_url: str) -> None:
    """Los envíos de `set_config`/`set_rate` no se anotan en el registro, pero sus `error` sí."""
    errors = [
        {"type": "error", "v": 1, "t_ms": 2000, "code": "out_of_range", "cmd": "set_config",
         "message": "base_speed fuera de rango"},
        {"type": "error", "v": 1, "t_ms": 2500, "code": "out_of_range", "cmd": "set_rate",
         "message": "hz fuera de rango"},
    ]
    FakeServer(page, lambda connection: connection.send(SIM_HELLO, SIM_CONFIG, *errors))
    page.goto(live_url)

    log = _by_id(page, "log")
    expect(log.locator('li[data-kind="error"]')).to_have_count(2)
    expect(log.locator("li").nth(0)).to_contain_text("✕ out_of_range · set_rate · hz fuera de rango")
    expect(log.locator("li").nth(1)).to_contain_text("✕ out_of_range · set_config · base_speed fuera de rango")
    expect(log.locator("li").nth(0)).to_contain_text("2.500 s")
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    assert capture.console_errors == []


def _set_lap_target(page: Page, text: str) -> None:
    field = _by_id(page, "lap-target-input")
    field.fill(text)
    field.press("Enter")


def _run_laps(server: FakeServer, laps: int, extra_telemetry: int = 3) -> None:
    """La corrida `r-1`: arranque, `laps` vueltas y varias telemetrías con el último `lap.n`."""
    connection = server.last
    connection.send(event("run_started", "r-1", 2000), telemetry(SIM_HELLO, 1, run_id="r-1"))
    seq = 1
    for n in range(1, laps + 1):
        seq += 1
        connection.send(event("lap", "r-1", 2000 + n * 3000, lap=n, lap_ms=3000), telemetry(SIM_HELLO, seq, run_id="r-1", lap_n=n))
    for _ in range(extra_telemetry):
        seq += 1
        connection.send(telemetry(SIM_HELLO, seq, run_id="r-1", lap_n=laps))


def test_lap_target_sends_a_single_stop(page: Page, capture: Capture, live_url: str) -> None:
    server = FakeServer(page, open_session(SIM_HELLO, SIM_CONFIG))
    page.goto(live_url)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    _set_lap_target(page, "2")
    expect(_by_id(page, "lap-target-input")).not_to_have_attribute("aria-invalid", "true")

    _run_laps(server, 2, extra_telemetry=5)
    _wait_for(lambda: len(server.commands("stop")) == 1, page)
    expect(_by_id(page, "lap-target")).to_have_text(" / 2")
    page.wait_for_timeout(300)
    assert len(server.commands("stop")) == 1
    assert capture.console_errors == []


def test_empty_or_invalid_lap_target_never_stops(page: Page, capture: Capture, live_url: str) -> None:
    server = FakeServer(page, open_session(SIM_HELLO, SIM_CONFIG))
    page.goto(live_url)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")

    for text in ("0", "1.5"):
        _set_lap_target(page, text)
        expect(_by_id(page, "lap-target-input")).to_have_attribute("aria-invalid", "true")

    _run_laps(server, 3)
    expect(_by_id(page, "lap-n")).to_have_text("3")
    page.wait_for_timeout(300)
    assert server.commands("stop") == []

    _set_lap_target(page, "")
    expect(_by_id(page, "lap-target-input")).to_have_attribute("aria-invalid", "false")
    page.wait_for_timeout(200)
    assert server.commands("stop") == []
    assert capture.console_errors == []


def test_unknown_track_on_connect_is_shown(page: Page, capture: Capture, live_url: str) -> None:
    """Como el simulador ante `?track=no-existe`: abre igual y avisa con un `error` sin `cmd`."""
    unknown = {"type": "error", "v": 1, "t_ms": 1, "code": "unknown_track",
               "message": "la pista «no-existe» no está en el catálogo; se usa oval-01"}
    FakeServer(page, lambda connection: connection.send(SIM_HELLO, SIM_CONFIG, unknown))
    page.goto(live_url)
    error = _by_id(page, "log").locator('li[data-kind="error"]')
    expect(error).to_have_count(1)
    expect(error).to_contain_text("unknown_track")
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    assert capture.console_errors == []


def test_reconnect_reuses_the_chosen_track(page: Page, capture: Capture, live_url: str) -> None:
    """Tras cambiar de pista, Reconectar repite `track` y `robot` de la última conexión."""
    server = FakeServer(page, open_session(SIM_HELLO, SIM_CONFIG))
    page.goto(live_url)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    _open_robot_track_tab(page)
    page.once("dialog", lambda dialog: dialog.accept())
    _by_id(page, "track-select").select_option("oval-01")
    _wait_for(lambda: len(server.connections) == 2, page)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")

    server.last.close()
    expect(_by_id(page, "btn-reconnect")).to_be_visible()
    _by_id(page, "btn-reconnect").click()
    _wait_for(lambda: len(server.connections) == 3, page)
    urls = [connection.url for connection in server.connections]
    assert "track=oval-01" in urls[1] and "robot=velocista-01" in urls[1]
    assert urls[2] == urls[1]
    assert capture.console_errors == []


def test_server_closing_shows_disconnected(page: Page, capture: Capture, live_url: str) -> None:
    server = FakeServer(page, open_session(SIM_HELLO, SIM_CONFIG))
    page.goto(live_url)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    server.last.close()
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "closed")
    expect(_by_id(page, "conn-status")).to_have_text("DESCONECTADO")
    expect(_by_id(page, "btn-reconnect")).to_be_visible()
    expect(_by_id(page, "btn-start")).to_be_disabled()
    expect(_by_id(page, "lap-target-input")).to_be_disabled()
    expect(_by_id(page, "kp-input")).to_be_disabled()
    expect(_by_id(page, "kp-range")).to_be_disabled()
    expect(_by_id(page, "rate-input")).to_be_disabled()
    assert capture.console_errors == []


def test_full_server_then_reconnect(page: Page, capture: Capture, live_url: str) -> None:
    """Como el simulador con las sesiones al máximo: acepta y cierra con 1013 sin `hello`."""
    server = FakeServer(page)
    page.goto(live_url)
    _wait_for(lambda: len(server.connections) == 1, page)
    server.last.close(code=1013)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "closed")
    expect(page.locator('[data-role="conn-message"]')).to_contain_text("Servidor lleno")
    expect(_by_id(page, "btn-reconnect")).to_be_visible()

    _by_id(page, "btn-reconnect").click()
    _wait_for(lambda: len(server.connections) == 2, page)
    server.last.send(SIM_HELLO, SIM_CONFIG)
    expect(_by_id(page, "conn-status")).to_have_attribute("data-state", "open")
    expect(_by_id(page, "robot-id")).to_have_text("velocista-01")
    expect(_by_id(page, "btn-reconnect")).to_be_hidden()
    assert capture.console_errors == []
