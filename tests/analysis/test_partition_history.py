"""Test cho `src/analysis/partition_history.py` — lịch sử "đạt ở k trong m cách chia" (ADR-0024)."""

from src.analysis.partition_history import (
    PartitionHistory,
    RunLabels,
    StoredComparison,
    display_direction,
    distinct_partitions,
    partition_history,
    partition_run_ids,
    representatives,
)
from src.analysis.topic_comparison import Metric

A = {"u1": 0, "u2": 0, "u3": -1}
B = {"u1": 0, "u2": 1, "u3": -1}
ALPHA = 0.05


def _cmp(
    run_id: int,
    effect: float | None,
    p_holm: float | None,
    *,
    topic: str = "topic_1",
    metric: Metric = "engagement",
    insufficient: bool = False,
) -> StoredComparison:
    return StoredComparison(
        cluster_run_id=run_id,
        run_at=f"2026-10-{run_id:02d}T10:30:00+00:00",
        group_id=topic,
        metric=metric,
        effect_size=effect,
        p_value_holm=p_holm,
        insufficient_data=insufficient,
    )


# --- cách chia ------------------------------------------------------------------------------


def test_runs_with_identical_labels_share_the_previous_partition() -> None:
    # Cùng dữ liệu + seed cố định → nhãn y hệt → cùng cách chia; thứ tự đầu vào không quan trọng;
    # quay lại nhãn A sau B là cách chia MỚI ("khác lần trước", ADR-0024)
    runs = [RunLabels(4, B), RunLabels(2, A), RunLabels(3, A), RunLabels(5, B), RunLabels(6, A)]

    groups = distinct_partitions(runs)

    assert [[run.id for run in group] for group in groups] == [[2, 3], [4, 5], [6]]


def test_a_new_unit_opens_a_new_partition() -> None:
    # ARI chỉ tính trên unit chung: thêm 1 bài mới (vào nhiễu) vẫn ra ARI 1.0 — nhưng là dữ liệu
    # khác, nên phải là cách chia mới (code-reviewer 2026-10-18)
    grown = {**A, "u4": -1}

    assert partition_run_ids([(1, A), (2, grown)]) == [[1], [2]]


def test_partition_run_ids_matches_distinct_partitions() -> None:
    assert partition_run_ids([(1, A), (2, A), (3, B)]) == [[1, 2], [3]]


def test_representative_is_the_latest_compared_run_of_each_partition() -> None:
    # Lần 3 (cuối cách chia 1) chưa có kết quả so sánh (bước so sánh lỗi) → đại diện là lần 2;
    # cách chia [4] không có lần so sánh nào → bỏ
    assert representatives([[1, 2, 3], [4], [5, 6]], {1, 2, 5, 6}) == [2, 6]


# --- k trong m ------------------------------------------------------------------------------


def test_each_partition_counts_once_using_its_latest_comparison() -> None:
    # Cách chia [1, 2]: lần 1 đạt, lần 2 (mới nhất, số views đầy đủ hơn) không đạt → không đạt.
    # Lấy "đạt ở bất kỳ lần nào" sẽ ra higher = 2 — đột biến này phải làm test fail
    stored = [_cmp(1, 0.6, 0.01), _cmp(2, 0.5, 0.20), _cmp(3, 0.6, 0.01)]

    history = partition_history([[1, 2], [3]], stored, alpha=ALPHA)

    assert history[("topic_1", "engagement")] == PartitionHistory(
        clusterings=2, higher=1, lower=0, too_few_posts=0, since="2026-10-02T10:30:00+00:00"
    )


def test_too_few_posts_is_not_a_failed_test() -> None:
    # Ca topic_11 thật (2026-10-20): 4 bài → thiếu bài; rồi đạt, đạt, không đạt → "2 of 3", không
    # phải "2 of 4" (Thy chốt m chỉ gồm cách chia kiểm định được)
    stored = [
        _cmp(1, 0.52, 1.0, insufficient=True),
        _cmp(2, 0.60, 0.0005),
        _cmp(3, 0.53, 0.0144),
        _cmp(4, 0.58, 0.0708),
    ]

    history = partition_history([[1], [2], [3], [4]], stored, alpha=ALPHA)[
        ("topic_1", "engagement")
    ]

    assert (history.clusterings, history.higher, history.too_few_posts) == (3, 2, 1)
    # lịch sử bắt đầu từ lần đầu topic xuất hiện, kể cả khi lần đó thiếu bài
    assert history.since == "2026-10-01T10:30:00+00:00"


def test_missing_p_counts_as_untestable() -> None:
    history = partition_history([[1], [2]], [_cmp(1, None, None), _cmp(2, 0.4, 0.01)], alpha=ALPHA)

    assert history[("topic_1", "engagement")].clusterings == 1
    assert history[("topic_1", "engagement")].too_few_posts == 1


def test_direction_is_counted_separately() -> None:
    stored = [_cmp(1, 0.6, 0.01), _cmp(2, -0.6, 0.01), _cmp(3, -0.5, 0.02)]

    history = partition_history([[1], [2], [3]], stored, alpha=ALPHA)[("topic_1", "engagement")]

    assert (history.higher, history.lower, history.clusterings) == (1, 2, 3)


def test_alpha_is_a_strict_threshold() -> None:
    history = partition_history([[1]], [_cmp(1, 0.6, ALPHA)], alpha=ALPHA)

    assert history[("topic_1", "engagement")].higher == 0


def test_topics_and_metrics_are_tracked_independently() -> None:
    # topic_2 chỉ có từ cách chia 2 (id mới sau gộp/tách → lịch sử bắt đầu lại)
    stored = [
        _cmp(1, 0.6, 0.01),
        _cmp(1, 0.6, 0.01, metric="share_rate"),
        _cmp(2, 0.6, 0.30),
        _cmp(2, 0.6, 0.01, topic="topic_2"),
    ]

    history = partition_history([[1], [2]], stored, alpha=ALPHA)

    assert history[("topic_1", "engagement")].clusterings == 2
    assert history[("topic_1", "share_rate")].clusterings == 1
    assert history[("topic_2", "engagement")] == PartitionHistory(
        clusterings=1, higher=1, lower=0, too_few_posts=0, since="2026-10-02T10:30:00+00:00"
    )


def test_no_comparisons_gives_no_history() -> None:
    assert partition_history([[1, 2]], [], alpha=ALPHA) == {}


# --- hướng hiển thị (ô "stood out in") -------------------------------------------------------


def _history(higher: int, lower: int) -> PartitionHistory:
    return PartitionHistory(
        clusterings=5, higher=higher, lower=lower, too_few_posts=0, since="2026-10-09"
    )


def test_no_pass_has_no_direction() -> None:
    # k = 0 không có hướng — gắn "below" theo δ âm là nói quá dữ liệu (copy-reviewer 2026-10-20)
    assert display_direction(_history(0, 0), -0.5) is None


def test_single_direction_wins_over_the_current_delta() -> None:
    # Chỉ từng đạt "thấp hơn": δ hiện tại dương không được lật hướng thành "cao hơn 0 of 5"
    assert display_direction(_history(0, 2), 0.2) == "lower"
    assert display_direction(_history(2, 0), -0.2) == "higher"


def test_both_directions_follow_the_current_delta_then_the_larger_count() -> None:
    assert display_direction(_history(2, 1), -0.3) == "lower"
    assert display_direction(_history(1, 2), None) == "lower"  # δ ẩn (stale) → hướng nhiều hơn
    assert display_direction(_history(1, 1), 0.0) == "higher"  # hoà → higher (UI ghi mũi tên)
