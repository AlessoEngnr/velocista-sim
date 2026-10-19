"""El panel se sirve en `/` sin romper `/health` ni `/ws` (specs/003-panel-laboratorio,
contracts/http-panel.md, FR-001)."""

from __future__ import annotations

import json
import re
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from support.session_driver import CONFIG_DIR
from velocista_sim.contract import validate_message
from velocista_sim.server.app import STATIC_DIR, create_app
from velocista_sim.server.settings import Settings

STATIC_FILES = sorted(path for path in STATIC_DIR.rglob("*") if path.is_file())
URL_PATTERN = re.compile(r"https?://\S*")
ALLOWED_URL_PREFIX = "http://www.w3.org/"


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app(Settings(config_dir=CONFIG_DIR))) as test_client:
        yield test_client


def _published_path(path) -> str:
    return "/" + path.relative_to(STATIC_DIR).as_posix()


def test_root_serves_the_panel(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>Panel de laboratorio" in response.text


def test_required_assets_exist() -> None:
    """Sin estos archivos el test de MIME no comprobaría nada."""
    assert (STATIC_DIR / "js" / "main.js").is_file()
    assert (STATIC_DIR / "panel.css").is_file()


@pytest.mark.parametrize(
    ("suffix", "mime"), [(".js", "text/javascript"), (".css", "text/css")], ids=["js", "css"]
)
def test_assets_have_the_right_mime(client: TestClient, suffix: str, mime: str) -> None:
    files = [path for path in STATIC_FILES if path.suffix == suffix]
    assert files, f"no hay archivos {suffix} en static/"
    for path in files:
        response = client.get(_published_path(path))
        assert response.status_code == 200, _published_path(path)
        assert response.headers["content-type"].startswith(mime), (
            f"{_published_path(path)}: {response.headers['content-type']}"
        )


def test_unknown_path_is_404(client: TestClient) -> None:
    assert client.get("/no-existe.js").status_code == 404


def test_health_still_works(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ws_still_works(client: TestClient) -> None:
    with client.websocket_connect("/ws") as websocket:
        hello = json.loads(websocket.receive_text())
        assert hello["type"] == "hello"
        assert validate_message(hello).ok
        config = json.loads(websocket.receive_text())
        assert config["type"] == "config"
        assert validate_message(config, hello).ok


def test_static_files_do_not_reach_other_origins() -> None:
    problems: list[str] = []
    for path in STATIC_FILES:
        text = path.read_text(encoding="utf-8")
        name = _published_path(path)
        for scheme in ("ws://", "wss://"):
            if scheme in text:
                problems.append(f"{name}: contiene {scheme} literal")
        for url in URL_PATTERN.findall(text):
            if not url.startswith(ALLOWED_URL_PREFIX):
                problems.append(f"{name}: URL externa {url}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("path", ["/", *[_published_path(path) for path in STATIC_FILES]])
def test_static_files_are_always_revalidated(client: TestClient, path: str) -> None:
    """`Cache-Control: no-cache`: tras un despliegue el navegador revalida cada módulo y nunca
    mezcla archivos de versiones distintas (contracts/http-panel.md)."""
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    # La revalidación responde 304 con el mismo encabezado.
    etag = response.headers.get("etag")
    if etag:
        again = client.get(path, headers={"If-None-Match": etag})
        assert again.status_code == 304
        assert again.headers["cache-control"] == "no-cache"


def test_health_is_not_affected_by_the_panel_cache_policy(client: TestClient) -> None:
    assert "cache-control" not in client.get("/health").headers


def test_page_declares_a_favicon_that_exists(client: TestClient) -> None:
    """El panel declara su ícono, así el navegador no pide `/favicon.ico` y la consola no
    muestra un 404."""
    html = client.get("/").text
    match = re.search(r'<link rel="icon" href="([^"]+)" type="image/svg\+xml">', html)
    assert match, "index.html no declara el favicon"
    icon = client.get("/" + match.group(1))
    assert icon.status_code == 200
    assert icon.headers["content-type"].startswith("image/svg+xml")
    assert icon.headers["cache-control"] == "no-cache"
