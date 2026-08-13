FROM node:20-slim AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=2.4.1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR=/tmp/poetry_cache \
    PORT=8080 \
    SCENARIO_DATA_DIR=/app/data/scenarios \
    STATIC_DIR=/app/app/static \
    LOG_LEVEL=INFO

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

COPY backend/pyproject.toml backend/poetry.lock ./
RUN poetry install --only main --no-root && rm -rf "$POETRY_CACHE_DIR"

COPY backend/app ./app
COPY backend/data ./data
COPY --from=frontend /web/dist ./app/static

RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/api/health" || exit 1

CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
