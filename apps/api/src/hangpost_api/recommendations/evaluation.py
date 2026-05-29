"""Offline evaluation of the recommendation ranker against baselines.

Pure functions (standard library only) so they unit-test in CI without a
database and can be reused by the Phase 7 retraining harness. The
DB-backed driver that pulls real impressions/outcomes lives in
``scripts/evaluate.py``.

Relevance is graded from the logged outcome of each impression — the
real signal the ML loop optimizes (CLAUDE.md §5):

    friend_request_sent / hangout_rsvped  → 3  (strong positive)
    profile_opened                        → 2
    viewed                                → 1
    nothing                               → 0

We score three rankings per query (one query = one ``/recommendations``
call): the live ranker (the order the API actually surfaced), a random
shuffle, and a popularity-only order (globally most-surfaced candidates
first). NDCG@10 rewards putting high-relevance items near the top;
Recall@10 measures how many of the relevant items made the top-k.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    """One surfaced candidate, with relevance derived from its outcome."""

    candidate_id: str
    rank_position: int  # 1-based position the live ranker assigned
    relevance: int  # graded label from the outcome (0–3)


def relevance_from_outcome(
    *,
    viewed: bool,
    profile_opened: bool,
    friend_request_sent: bool,
    hangout_rsvped: bool,
) -> int:
    """Graded relevance from an impression's outcome flags (0 if none)."""
    if friend_request_sent or hangout_rsvped:
        return 3
    if profile_opened:
        return 2
    if viewed:
        return 1
    return 0


def dcg(relevances: Sequence[int]) -> float:
    """Discounted cumulative gain with the standard 2**rel - 1 gain."""
    return sum((2**rel - 1) / math.log2(i + 2) for i, rel in enumerate(relevances))


def ndcg_at_k(relevances_in_rank_order: Sequence[int], k: int = 10) -> float:
    """NDCG@k. Returns 0.0 when there is no relevance signal (never NaN)."""
    top = list(relevances_in_rank_order[:k])
    ideal = sorted(relevances_in_rank_order, reverse=True)[:k]
    idcg = dcg(ideal)
    if idcg == 0.0:
        return 0.0
    return dcg(top) / idcg


def recall_at_k(relevances_in_rank_order: Sequence[int], k: int = 10) -> float:
    """Fraction of all relevant (rel > 0) items that land in the top k."""
    total_relevant = sum(1 for r in relevances_in_rank_order if r > 0)
    if total_relevant == 0:
        return 0.0
    hits = sum(1 for r in relevances_in_rank_order[:k] if r > 0)
    return hits / total_relevant


def _live_order(candidates: Sequence[Candidate]) -> list[int]:
    return [c.relevance for c in sorted(candidates, key=lambda c: c.rank_position)]


def _random_order(candidates: Sequence[Candidate], rng: random.Random) -> list[int]:
    shuffled = list(candidates)
    rng.shuffle(shuffled)
    return [c.relevance for c in shuffled]


def _popularity_order(
    candidates: Sequence[Candidate], popularity: Mapping[str, int]
) -> list[int]:
    ordered = sorted(
        candidates, key=lambda c: popularity.get(c.candidate_id, 0), reverse=True
    )
    return [c.relevance for c in ordered]


@dataclass(frozen=True)
class MethodScore:
    ndcg_at_10: float
    recall_at_10: float
    n_queries: int


def evaluate(
    queries: Sequence[Sequence[Candidate]],
    popularity: Mapping[str, int],
    *,
    k: int = 10,
    seed: int = 0,
) -> dict[str, MethodScore]:
    """Average NDCG@k and Recall@k across queries for each ranking method.

    ``queries`` is a list of candidate-lists (one per ``/recommendations``
    call); ``popularity`` maps candidate_id → global surfaced count. The
    random baseline is seeded so reports are reproducible.
    """
    rng = random.Random(seed)
    methods: dict[str, list[list[int]]] = {
        "live_ranker": [_live_order(q) for q in queries],
        "popularity": [_popularity_order(q, popularity) for q in queries],
        "random": [_random_order(q, rng) for q in queries],
    }
    n = len(queries)
    out: dict[str, MethodScore] = {}
    for name, per_query in methods.items():
        if n == 0:
            out[name] = MethodScore(0.0, 0.0, 0)
            continue
        ndcg = sum(ndcg_at_k(r, k) for r in per_query) / n
        recall = sum(recall_at_k(r, k) for r in per_query) / n
        out[name] = MethodScore(ndcg, recall, n)
    return out
