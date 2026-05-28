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
# Install CPU-only torch FIRST so sentence-transformers' transitive torch
# requirement is already satisfied and pip doesn't reach for the default
# wheel (which bundles CUDA / nvidia-cudnn — ~3 GB of dead weight on a
# CPU-only deploy and the cause of "No space left on device" on Codespaces).
RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install ./apps/api

# ---- runtime ----
FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# libgomp1 is the OpenMP runtime that sentence-transformers (via torch) and
# lightgbm dlopen at import time. Without it, importing hangpost_matching
# crashes with "libgomp.so.1: cannot open shared object file".
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY apps/api/alembic.ini apps/api/alembic.ini
COPY apps/api/alembic apps/api/alembic
COPY apps/api/src apps/api/src
COPY apps/api/scripts apps/api/scripts
# Seeds ship inside the image so `python -m hangpost_api.seed` works under
# the non-editable install used here (where __file__ lives in site-packages).
COPY apps/api/seeds apps/api/seeds

# Non-root for safety.
RUN useradd --create-home --uid 10001 appuser
USER appuser

WORKDIR /app/apps/api
EXPOSE 8000
CMD ["uvicorn", "hangpost_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
