"""Test quy tắc ghép danh tính cụm (`src/nlp/topic_identity.py`, ADR-0018)."""

from __future__ import annotations

import numpy as np

from src.nlp.topic_identity import TopicMatch, anchor_holds, match_topics, semantic_reference


def _prev(**topics: str) -> dict[str, str]:
    """`_prev(topic_a="u1 u2")` → {u1: topic_a, u2: topic_a}."""
    return {uid: topic for topic, uids in topics.items() for uid in uids.split()}


def _cur(*clusters: str, noise: str = "") -> dict[str, int]:
    labels = {uid: i for i, uids in enumerate(clusters) for uid in uids.split()}
    labels.update({uid: -1 for uid in noise.split()})
    return labels


def _event(m: dict[int, TopicMatch], cluster: int) -> str:
    return m[cluster].event


# --- quy tắc thành viên --------------------------------------------------------------


def test_identical_membership_keeps_ids() -> None:
    m = match_topics(_prev(topic_1="a b c", topic_2="d e f"), _cur("d e f", "a b c"))
    assert m[0] == TopicMatch(0, "kept", "topic_2", ("topic_2",), "membership")
    assert m[1] == TopicMatch(1, "kept", "topic_1", ("topic_1",), "membership")


def test_churn_like_real_run_3_to_4_is_kept() -> None:
    # Thật: cụm cũ 9 bài, cụm mới 10 bài, 6 bài chung (jaccard 0,46) → vẫn giữ
    cur = _cur("a b c d e f n1 n2 x y", noise="g h i")
    assert _event(match_topics(_prev(topic_1="a b c d e f g h i"), cur), 0) == "kept"


def test_posts_falling_into_noise_do_not_count_as_leaving() -> None:
    # 4/10 bài vào cụm mới, 6 bài sang NHIỄU → bỏ nhiễu: 4/4 → giữ (Thy chốt câu 1)
    prev = _prev(topic_1="a b c d e f g h i j")
    cur = _cur("a b c d", noise="e f g h i j")
    assert match_topics(prev, cur)[0].topic_id == "topic_1"
    # Biến thể cũ (tính nhiễu là rời đi) → mới, ghi nguồn
    assert match_topics(prev, cur, exclude_noise=False)[0] == TopicMatch(
        0, "new", None, ("topic_1",)
    )


def test_posts_moving_to_another_cluster_still_count_as_leaving() -> None:
    # 4 bài ở lại, 6 bài sang 1 cụm KHÁC (không phải nhiễu) → topic_1 không gửi đa số vào cụm 0
    prev = _prev(topic_1="a b c d e f g h i j")
    m = match_topics(prev, _cur("a b c d", "e f g h i j x y z w q"), semantic=False)
    assert _event(m, 0) == "new"


def test_core_keeps_name_and_small_fragment_is_new() -> None:
    # 14 bài → lõi 11 + mảnh 4 (3 bài cũ + 1 bài khác): lõi giữ tên (Thy chốt câu 2)
    prev = _prev(topic_1="a b c d e f g h i j k l m n")
    m = match_topics(prev, _cur("a b c d e f g h i j k", "l m n z"), semantic=False)
    assert m[0] == TopicMatch(0, "kept", "topic_1", ("topic_1",), "membership")
    assert m[1] == TopicMatch(1, "new", None, ("topic_1",))
    # Biến thể cũ (tách → tên mới hết): cả lõi mất tên
    old = match_topics(prev, _cur("a b c d e f g h i j k", "l m n z"), core_keeps=False)
    assert {_event(old, 0), _event(old, 1)} == {"split"}


def test_even_split_without_a_core_renames_every_child() -> None:
    prev = _prev(topic_1="a b c d e f g h")
    m = match_topics(prev, _cur("a b c d", "e f g h"), semantic=False)
    assert {_event(m, 0), _event(m, 1)} == {"split"}
    assert m[0].sources == m[1].sources == ("topic_1",)


def test_merge_of_two_topics_gets_a_new_identity() -> None:
    m = match_topics(_prev(topic_1="a b c", topic_2="d e f"), _cur("a b c d e f"))
    assert m[0] == TopicMatch(0, "merged", None, ("topic_1", "topic_2"))


def test_cluster_of_mostly_new_posts_is_new() -> None:
    m = match_topics(_prev(topic_1="a b c"), _cur("a b c", "n1 n2 n3 a2"))
    assert _event(m, 0) == "kept"
    assert m[1] == TopicMatch(1, "new", None, ())


def test_exact_half_is_not_a_majority() -> None:
    m = match_topics(_prev(topic_1="a b c d"), _cur("a b x y"), semantic=False)
    assert _event(m, 0) == "new"


def test_units_missing_from_this_run_do_not_count_as_leaving() -> None:
    assert _event(match_topics(_prev(topic_1="a b c d e"), _cur("a b")), 0) == "kept"


def test_no_previous_topics_means_everything_is_new() -> None:
    m = match_topics({}, _cur("a b", "c d", noise="e"))
    assert [x.event for x in m.values()] == ["new", "new"]


# --- bước ngữ nghĩa ------------------------------------------------------------------


def _vectors(**dirs: str) -> dict[str, np.ndarray]:
    """`_vectors(x="a b")`: các bài a, b có embedding hướng trục x (3 trục x, y, z)."""
    axes = {"x": [1.0, 0.0, 0.0], "y": [0.0, 1.0, 0.0], "z": [0.0, 0.0, 1.0]}
    return {u: np.array(axes[d]) for d, uids in dirs.items() for u in uids.split()}


def test_reference_is_max_similarity_between_two_different_old_topics() -> None:
    vec = _vectors(x="a b", y="c d", z="e f")
    assert semantic_reference(_prev(t1="a b", t2="c d", t3="e f"), vec) == 0.0
    assert semantic_reference(_prev(t1="a b"), vec) is None  # < 2 topic


def test_semantically_same_cluster_keeps_id_after_membership_reshuffle() -> None:
    # Thành viên xáo hết (bài cũ sang nhiễu, bài khác vào) nhưng nội dung cùng hướng x
    prev = _prev(t1="a b c d", t2="e f g h")
    vec = _vectors(x="a b c d p q r s", y="e f g h")
    cur = _cur("p q r s", "e f g h", noise="a b c d")
    m = match_topics(prev, cur, vec, semantic_reference(prev, vec))
    assert m[0].topic_id == "t1" and m[0].via == "semantic"
    assert m[0].similarity == 1.0
    assert m[1].via == "membership"


def test_semantic_step_never_rescues_a_merged_cluster() -> None:
    prev = _prev(t1="a b", t2="c d", t3="e f")
    vec = _vectors(x="a b c d", z="e f")  # t1, t2 cùng hướng → nhập vẫn rất giống t1
    m = match_topics(prev, _cur("a b c d", "e f"), vec, -1.0)
    assert _event(m, 0) == "merged"


def test_semantic_step_needs_similarity_above_the_reference_and_gives_each_id_once() -> None:
    prev = _prev(t1="a b c d", t2="e f g h")
    vec = _vectors(x="a b c d p q r s u v w k", y="e f g h")
    cur = _cur("p q r s", "u v w k", "e f g h", noise="a b c d")
    m = match_topics(prev, cur, vec, semantic_reference(prev, vec))
    assert sorted(x.topic_id or "-" for x in m.values()) == ["-", "t1", "t2"]
    # ngưỡng 1,0: cosine phải LỚN HƠN → không cụm nào được giữ nhờ ngữ nghĩa
    strict = match_topics(prev, cur, vec, 1.0)
    assert [x.via for x in strict.values()] == [None, None, "membership"]


# --- độ trôi so với bản neo lúc đặt tên ----------------------------------------------


def test_anchor_holds_while_cumulative_change_stays_under_half() -> None:
    anchor = set(["a", "b", "c", "d", "e", "f"])
    cur = _cur("a b c d x y")
    assert anchor_holds({"a", "b", "c", "d", "x", "y"}, anchor, cur)


def test_anchor_breaks_after_cumulative_drift_even_if_each_step_was_small() -> None:
    anchor = set(["a", "b", "c", "d", "e", "f"])
    cur = _cur("a b x y z w", noise="c d e f")  # 4/6 nội dung đã khác lúc đặt tên
    assert not anchor_holds({"a", "b", "x", "y", "z", "w"}, anchor, cur)


def test_anchor_holds_semantically_when_content_direction_is_unchanged() -> None:
    anchor = set(["a", "b", "c", "d"])
    vec = _vectors(x="a b c d p q r s")
    cur = _cur("p q r s", noise="a b c d")
    assert anchor_holds({"p", "q", "r", "s"}, anchor, cur, vec, 0.5)
    assert not anchor_holds({"p", "q", "r", "s"}, anchor, cur, vec, None)


def test_residual_of_a_topic_that_dissolved_into_noise_is_not_a_merge() -> None:
    # Q tan 9/10 bài vào nhiễu, 1 bài sót vào cụm tiếp nối của P → P vẫn giữ (code-reviewer)
    prev = _prev(P="a b c d e f", Q="q0 q1 q2 q3 q4 q5 q6 q7 q8 q9")
    cur = _cur("a b c d e f q0", noise="q1 q2 q3 q4 q5 q6 q7 q8 q9")
    assert match_topics(prev, cur, semantic=False)[0] == TopicMatch(
        0, "kept", "P", ("P",), "membership"
    )
    # Biến thể đã review (phép thử nhập cũng bỏ nhiễu): 1/1 bài của Q → nhập giả
    old = match_topics(prev, cur, semantic=False, merge_counts_noise=False)
    assert _event(old, 0) == "merged"


def test_parents_of_a_merge_do_not_hand_their_id_to_a_third_cluster() -> None:
    prev = _prev(t1="a b", t2="c d", t3="e f g h")
    vec = _vectors(x="a b c d k l m n", z="e f g h")
    cur = _cur("a b c d", "k l m n", "e f g h")  # t1+t2 nhập; cụm 1 cùng hướng với t1
    m = match_topics(prev, cur, vec, -1.0)
    assert _event(m, 0) == "merged"
    assert m[1].topic_id is None  # t1 đã nhập vào cụm 0 → không trao id cho cụm 1
    loose = match_topics(prev, cur, vec, -1.0, semantic_for_merged=True)
    assert loose[0].topic_id in {"t1", "t2"}  # biến thể thăm dò: cứu cả cụm nhập
