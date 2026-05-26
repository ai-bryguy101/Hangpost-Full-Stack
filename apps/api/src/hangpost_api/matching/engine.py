"""Adapter around the ``hangpost-matching`` package.

Phase 0 only establishes the seam. The engine is imported lazily so the
service (and CI) boots even before the package is pinned/installed; the
real wiring lands in Phase 3 (CLAUDE.md §6).

The radius is a HARD pre-filter applied *before* this adapter runs —
distance never enters the score (CLAUDE.md §2).
"""

from importlib import import_module
from typing import Any


def is_available() -> bool:
    """Return True if the matching engine package can be imported."""
    try:
        import_module("hangpost_matching")
    except ImportError:
        return False
    return True


def rank(source: Any, candidates: list[Any]) -> list[Any]:
    """Rank pre-filtered ``candidates`` for ``source``.

    Delegates to ``hangpost_matching.rank``. Callers are responsible for
    applying the PostGIS radius pre-filter (and block filtering) to
    ``candidates`` before passing them here.
    """
    matching = import_module("hangpost_matching")
    ranked: list[Any] = matching.rank(source, candidates)
    return ranked
