"""Adapter around the ``hangpost-matching`` package.

This is the in-process seam to the sibling-repo ranker. The engine is
imported lazily so the service (and CI) boots even when the package is
unavailable (e.g. on a stale image); callers should gate on
:func:`is_available` first.

The radius is a HARD pre-filter applied *before* this adapter runs —
distance never enters the score (CLAUDE.md §2).
"""

from collections.abc import Mapping, Sequence
from importlib import import_module
from typing import Any


def is_available() -> bool:
    """Return True if the matching engine package can be imported."""
    try:
        import_module("hangpost_matching")
    except ImportError:
        return False
    return True


def rank(
    source: Any,
    candidates: list[Any],
    profile_embeddings: Mapping[str, Sequence[float]] | None = None,
) -> list[tuple[Any, Any]]:
    """Rank pre-filtered ``candidates`` for ``source``.

    Delegates to ``hangpost_matching.rank_candidates_with_cold_start``,
    which returns ``[(UserProfile, MatchBreakdown), ...]`` in ranked
    order and falls back to a popularity prior for sparse sources.
    Callers are responsible for applying the PostGIS radius pre-filter
    (and block filtering) before passing candidates here.
    """
    matching = import_module("hangpost_matching")
    ranked: list[tuple[Any, Any]] = matching.rank_candidates_with_cold_start(
        source, candidates, profile_embeddings=profile_embeddings
    )
    return ranked
