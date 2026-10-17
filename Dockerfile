# Imagen del simulador velocista-sim (research R14). Railway la construye desde este archivo.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# El servidor busca contract/ y config/ subiendo desde el paquete: van junto a src/.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY contract ./contract
COPY config ./config
RUN uv sync --locked --no-dev

# Railway asigna PORT; en local el defecto es 8000.
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "velocista-sim"]
