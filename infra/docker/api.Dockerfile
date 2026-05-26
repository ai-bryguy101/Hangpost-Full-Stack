# Build context is the repo root (see infra/compose/docker-compose.yml).
# Multi-stage: install into a venv, then copy the venv into a slim runtime.

FROM python:3.12-slim AS builder
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# git is needed while the matching engine is a git dependency.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv "$VIRTUAL_ENV"

COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/api/src apps/api/src
RUN pip install ./apps/api

# ---- runtime ----
FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=builder /opt/venv /opt/venv
COPY apps/api/alembic.ini apps/api/alembic.ini
COPY apps/api/alembic apps/api/alembic
COPY apps/api/src apps/api/src

# Non-root for safety.
RUN useradd --create-home --uid 10001 appuser
USER appuser

WORKDIR /app/apps/api
EXPOSE 8000
CMD ["uvicorn", "hangpost_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
