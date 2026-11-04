FROM python:3.13-slim AS base

# uv installs exactly what uv.lock pins, without the dev tools. The venv lives
# outside /app so `COPY . .` can never shadow it, and is first on PATH so
# uvicorn, arq and alembic run directly (docker-compose relies on that).
COPY --from=ghcr.io/astral-sh/uv:0.9.25 /uv /bin/uv
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

# Build deps for lxml / asyncmy.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first, so editing the code doesn't reinstall them.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .

EXPOSE 8000

# Default command runs the API; the worker overrides this in docker-compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
