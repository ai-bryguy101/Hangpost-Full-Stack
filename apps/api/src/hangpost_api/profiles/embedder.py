"""Process-cached sentence-transformer wrapper for profile writes.

The matching engine deliberately does *not* load a model itself — it
expects callers to pass a precomputed embedding map (see
``hangpost_matching.embeddings``). The API owns that step.

The model is loaded on the first call rather than at import time so
``/health`` stays fast and the docker readiness probe doesn't have to
wait on a ~90 MB weight download. Subsequent calls reuse the same
in-memory model.

``encode()`` is synchronous and CPU-bound (PyTorch under the hood);
async callers must use :func:`embed_profile_fields`, which hands the
work off to a worker thread so the event loop stays free.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from hangpost_matching import UserProfile, profile_to_text

from hangpost_api.profiles.models import EMBEDDING_DIM

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# `Any` instead of the concrete SentenceTransformer type so importing
# this module never pulls in torch — only callers that actually embed
# pay the import cost (see `_get_model`).
_model: Any = None
_lock = threading.Lock()


def _get_model() -> Any:
    """Return the singleton model, loading it on first access.

    ``sentence_transformers`` is imported here (not at module top) so
    the ~2s torch import is paid lazily — health checks and unit tests
    that never touch the embedder stay fast.
    """
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _build_engine_profile(
    user_id: str,
    *,
    interests: list[str],
    liked_topics: list[str],
    hometown: str | None,
    college: str | None,
    age: int | None,
) -> UserProfile:
    """Cast the app's profile fields into the engine's frozen dataclass."""
    return UserProfile(
        user_id=user_id,
        interests=set(interests),
        liked_topics=set(liked_topics),
        hometown=hometown,
        college=college,
        age=age,
    )


def _embed_sync(
    user_id: str,
    *,
    interests: list[str],
    liked_topics: list[str],
    hometown: str | None,
    college: str | None,
    age: int | None,
) -> tuple[str, list[float] | None]:
    """Synthesize bio text + encode it. Empty profile -> ``("", None)``."""
    text = profile_to_text(
        _build_engine_profile(
            user_id,
            interests=interests,
            liked_topics=liked_topics,
            hometown=hometown,
            college=college,
            age=age,
        )
    )
    if not text:
        return "", None
    vector = _get_model().encode([text])[0]
    embedding = [float(x) for x in vector]
    if len(embedding) != EMBEDDING_DIM:
        raise RuntimeError(
            f"Embedding dim {len(embedding)} != schema dim {EMBEDDING_DIM}. "
            f"Did the engine switch models?"
        )
    return text, embedding


async def embed_profile_fields(
    user_id: str,
    *,
    interests: list[str],
    liked_topics: list[str],
    hometown: str | None,
    college: str | None,
    age: int | None,
) -> tuple[str, list[float] | None]:
    """Async wrapper: runs the blocking encode in a worker thread."""
    return await asyncio.to_thread(
        _embed_sync,
        user_id,
        interests=interests,
        liked_topics=liked_topics,
        hometown=hometown,
        college=college,
        age=age,
    )
