"""Test phần tính toán của thí nghiệm ADR-0018 (`scripts/topic_identity_eval.py`) — data giả."""

from __future__ import annotations

import numpy as np

from scripts import topic_identity_eval as ev

AXES = {"x": np.array([1.0, 0.0]), "y": np.array([0.0, 1.0])}
CHOSEN = ev.VARIANTS[-1][1]
MEMBERSHIP_ONLY = {"semantic": False}


def _reshuffle_case() -> tuple[dict[str, int], dict[str, int], dict[str, np.ndarray]]:
    """Topic 0 (hướng x) tan vào nhiễu, cụm mới cùng hướng x gồm bài khác; topic 1 giữ nguyên."""
    vectors = {u: AXES["x"] for u in ["a", "b", "c", "d", "p", "q", "r", "s"]} | {
        u: AXES["y"] for u in ["e", "f", "g", "h"]
    }
    prev = {u: 0 for u in ["a", "b", "c", "d"]} | {u: 1 for u in ["e", "f", "g", "h"]}
    cur = {u: 0 for u in ["p", "q", "r", "s"]} | {u: 1 for u in ["e", "f", "g", "h"]}
    cur |= {u: -1 for u in ["a", "b", "c", "d"]}
    return prev, cur, vectors


def test_variants_end_with_the_chosen_production_defaults() -> None:
    assert ev.VARIANTS[-1][0].endswith("(chosen)") and CHOSEN == {}
    assert ev.VARIANTS[0][1] == {"exclude_noise": False, "core_keeps": False, "semantic": False}


def test_flip_margin_counts_posts_until_majority_is_lost() -> None:
    assert ev.flip_margin(6, 10) == 1  # 5/10 không còn là đa số
    assert ev.flip_margin(9, 9) == 5  # 4/9 ≤ 1/2
    assert ev.flip_margin(2, 4) == 0  # đã không là đa số


def test_as_topics_drops_noise() -> None:
    assert ev.as_topics({"a": 0, "b": -1, "c": 1}) == {"a": "t0", "c": "t1"}


def test_evaluate_pair_flags_renames_that_are_closer_than_the_reference() -> None:
    prev, cur, vectors = _reshuffle_case()
    membership = ev.evaluate_pair(prev, cur, vectors, MEMBERSHIP_ONLY)
    assert sorted(r["event"] for r in membership) == ["kept", "new"]
    renamed = next(r for r in membership if r["event"] == "new")
    assert renamed["best_cosine"] == 1.0 and renamed["reference"] == 0.0
    chosen = ev.evaluate_pair(prev, cur, vectors, CHOSEN)
    assert sorted(r["via"] for r in chosen) == ["membership", "semantic"]


def test_false_keeps_detects_an_id_surviving_a_removed_topic() -> None:
    prev, cur, vectors = _reshuffle_case()
    cur |= {u: 2 for u in ["k", "l", "m", "n"]}  # cụm thứ 3 cùng hướng x
    vectors |= {u: AXES["x"] for u in ["k", "l", "m", "n"]}
    rows = ev.evaluate_pair(prev, cur, vectors, CHOSEN)
    wrong, trials = ev.false_keeps(prev, cur, vectors, CHOSEN, rows)
    # Xoá cụm đang giữ t0 → cụm x còn lại lấy id t0 dù topic t0 đã bị xoá hẳn
    assert trials == 2 and wrong == 1
    assert ev.false_keeps(prev, cur, vectors, MEMBERSHIP_ONLY, rows)[0] == 0


def test_membership_margins_of_identical_runs() -> None:
    labels = {u: 0 for u in ["a", "b", "c", "d"]} | {"e": -1}
    [row] = ev.membership_margins(labels, labels)
    assert row["share_new"] == row["share_old"] == 1.0
    assert row["posts_to_flip"] == 2


def test_two_way_bootstrap_resamples_seeds_and_skips_identical_pairs() -> None:
    seeds = ["s1", "s2", "s3"]
    values = {(a, b): 0.1 * (int(a[1]) + int(b[1])) for a in seeds for b in seeds if a != b}
    lo, hi = ev.pair_bootstrap(values, seeds, reps=500)
    assert lo <= sum(values.values()) / len(values) <= hi
    assert ev.pair_bootstrap(values, seeds, reps=500) == (lo, hi)  # tất định (seed 0)
    constant = {k: 0.3 for k in values}
    assert ev.pair_bootstrap(constant, seeds, reps=200) == (0.3, 0.3)
