"""Unit tests for the pure offline-evaluation metrics.

No database or network — exercises the stdlib math in
``hangpost_api.recommendations.evaluation`` so the ML-loop measurement
story is verifiable in CI.
"""

from hangpost_api.recommendations.evaluation import (
    Candidate,
    evaluate,
    ndcg_at_k,
    recall_at_k,
    relevance_from_outcome,
)


def test_relevance_grading_is_ordered() -> None:
    def rel(**flags: bool) -> int:
        base = {
            "viewed": False,
            "profile_opened": False,
            "friend_request_sent": False,
            "hangout_rsvped": False,
        }
        base.update(flags)
        return relevance_from_outcome(**base)

    assert rel(friend_request_sent=True) == 3
    assert rel(hangout_rsvped=True) == 3
    assert rel(viewed=True, profile_opened=True) == 2
    assert rel(viewed=True) == 1
    assert rel() == 0


def test_ndcg_perfect_ranking_is_one() -> None:
    # Already in descending relevance order → NDCG == 1.0.
    assert ndcg_at_k([3, 2, 1, 0], k=10) == 1.0


def test_ndcg_reversed_ranking_is_below_perfect() -> None:
    assert ndcg_at_k([0, 1, 2, 3], k=10) < ndcg_at_k([3, 2, 1, 0], k=10)


def test_ndcg_all_zero_is_zero_not_nan() -> None:
    value = ndcg_at_k([0, 0, 0], k=10)
    assert value == 0.0


def test_recall_at_k_counts_relevant_in_topk() -> None:
    # 3 relevant items total; top-2 contains 1 of them → 1/3.
    assert recall_at_k([1, 0, 2, 3], k=2) == 1 / 3
    assert recall_at_k([0, 0, 0], k=2) == 0.0


def test_evaluate_live_ranker_beats_random_when_signal_is_ordered() -> None:
    # One query where the live ranker put the only positive at the top.
    query = [
        Candidate("a", rank_position=1, relevance=3),
        Candidate("b", rank_position=2, relevance=0),
        Candidate("c", rank_position=3, relevance=0),
    ]
    scores = evaluate([query], popularity={"a": 1, "b": 1, "c": 1}, seed=0)
    assert scores["live_ranker"].n_queries == 1
    assert scores["live_ranker"].ndcg_at_10 == 1.0
    assert scores["live_ranker"].ndcg_at_10 >= scores["random"].ndcg_at_10


def test_evaluate_empty_is_all_zero() -> None:
    scores = evaluate([], popularity={})
    assert scores["live_ranker"] == scores["random"]
    assert scores["live_ranker"].n_queries == 0
    assert scores["live_ranker"].ndcg_at_10 == 0.0
