"""velocista-sim: simulador de un robot velocista seguidor de línea, accesible por WebSocket."""

import logging
import os


def main() -> None:
    """Arranca el servidor en `0.0.0.0:$PORT` (por defecto 8000) con `/ws`."""
    import uvicorn

    from .server.app import create_app
    from .server.settings import Settings

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env(os.environ)
    uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port, proxy_headers=True)
