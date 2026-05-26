"""FastAPI application entrypoint.

Phase 0 wires the app shell: settings, structured logging, a request-id
middleware (observability from day one — CLAUDE.md §8), and a health
check. Domain routers are mounted as each phase lands.
"""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from hangpost_api import __version__
from hangpost_api.core.config import get_settings
from hangpost_api.core.db import engine

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

REQUEST_ID_HEADER = "X-Request-ID"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Dispose the database engine cleanly on shutdown."""
    log.info("startup", version=__version__, environment=get_settings().environment)
    yield
    await engine.dispose()


app = FastAPI(
    title="Hangpost API",
    version=__version__,
    lifespan=lifespan,
)

# allow_credentials=True is required so the browser sends the Clerk httpOnly
# cookie; that forbids a "*" origin, hence the explicit allow-list.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER],
)


@app.middleware("http")
async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Attach a request id to every request, generating one if absent."""
    request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    structlog.contextvars.clear_contextvars()
    return response


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe — does not touch dependencies."""
    return {"status": "ok", "version": __version__}


@app.get("/health/ready", tags=["meta"])
async def ready() -> dict[str, str]:
    """Readiness probe — verifies the database is reachable."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ready"}
