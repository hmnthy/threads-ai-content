"""So sánh topic vs phần còn lại của kênh (ADR-0023) — `compare_topics`."""

import pytest

from src.analysis.significance import compare_groups, holm_adjust
from src.analysis.stats import MIN_N_PER_BUCKET
from src.analysis.topic_comparison import (
    CHANNEL_GROUP,
    METRICS,
    NOISE_GROUP,
    GroupComparison,
    UnitObservation,
    compare_topics,
)
from src.api.models import PostInsights

N_PERM = 500  # đủ để kiểm cấu trúc; số thật dùng mặc định 100.000


def _unit(
    unit_id: str,
    topic_id: str | None,
    *,
    views: int | None = 1000,
    likes: int = 0,
    replies: int = 0,
) -> UnitObservation:
    insights = (
        None
        if views is None
        else PostInsights(post_id=unit_id, views=views, likes=likes, replies=replies, reposts=0)
    )
    return UnitObservation(unit_id=unit_id, topic_id=topic_id, insights=insights)


def _channel() -> list[UnitObservation]:
    """topic_a: 6 bài engagement cao; topic_b: 3 bài (dưới MIN_N_PER_BUCKET); 7 bài nhiễu; cộng 1
    bài views = 0 trong topic_a và 1 bài nhiễu chưa có snapshot."""
    units = [_unit(f"a{i}", "topic_a", likes=80 + i, replies=i) for i in range(6)]
    units.append(_unit("a_zero", "topic_a", views=0))
    units += [_unit(f"b{i}", "topic_b", likes=10 + 2 * i) for i in range(3)]
    units += [_unit(f"n{i}", None, likes=5 + 3 * i, replies=i % 2) for i in range(7)]
    units.append(_unit("n_no_snapshot", None, views=None))
    return units


def _row(rows: list[GroupComparison], group_id: str, metric: str) -> GroupComparison:
    (row,) = [r for r in rows if r.group_id == group_id and r.metric == metric]
    return row


def test_rows_cover_every_topic_metric_plus_noise_and_channel() -> None:
    result = compare_topics(_channel(), n_permutations=N_PERM)

    keys = [(r.group_id, r.metric) for r in result.rows]
    assert len(keys) == len(set(keys)) == 4 * len(METRICS)  # 2 topic + nhiễu + kênh
    for metric in METRICS:
        assert _row(result.rows, NOISE_GROUP, metric).tested is False
        assert _row(result.rows, CHANNEL_GROUP, metric).tested is False
        assert _row(result.rows, "topic_a", metric).tested is True


def test_holm_family_counts_small_topics_and_matches_holm_adjust() -> None:
    result = compare_topics(_channel(), n_permutations=N_PERM)

    tested = [r for r in result.rows if r.tested]
    # topic_b có 3 bài < MIN_N_PER_BUCKET nhưng VẪN trong họ (ADR-0023 1c): 2 topic × 3 chỉ số
    assert _row(result.rows, "topic_b", "engagement").group.n < MIN_N_PER_BUCKET
    assert result.holm_family_size == len(tested) == 2 * len(METRICS)
    expected = holm_adjust([r.p_value for r in tested if r.p_value is not None])
    assert [r.p_value_holm for r in tested] == expected
    assert all(r.p_value_holm is None for r in result.rows if not r.tested)


def test_each_topic_is_compared_with_every_other_unit_including_noise() -> None:
    units = _channel()
    result = compare_topics(units, n_permutations=N_PERM)

    row = _row(result.rows, "topic_a", "engagement")
    topic_values = [
        u.insights.engagement_rate
        for u in units
        if u.topic_id == "topic_a" and u.insights is not None and u.insights.views > 0
    ]
    rest_values = [
        u.insights.engagement_rate
        for u in units
        if u.topic_id != "topic_a" and u.insights is not None and u.insights.views > 0
    ]
    direct = compare_groups(topic_values, rest_values, n_permutations=N_PERM, random_seed=0)
    assert row.effect_size == direct.effect_size
    assert row.p_value == direct.p_value
    assert (row.effect_size_ci_low, row.effect_size_ci_high) == (
        direct.effect_size_ci_low,
        direct.effect_size_ci_high,
    )
    assert row.effect_size is not None and row.effect_size > 0  # topic_a cao hơn phần còn lại


def test_zero_view_units_are_excluded_and_counted_units_without_snapshot_are_not() -> None:
    result = compare_topics(_channel(), n_permutations=N_PERM)

    topic_a = _row(result.rows, "topic_a", "engagement")
    assert (topic_a.group.n, topic_a.group_excluded_no_views) == (6, 1)
    noise = _row(result.rows, NOISE_GROUP, "engagement")
    assert (noise.group.n, noise.group_excluded_no_views) == (7, 0)
    channel = _row(result.rows, CHANNEL_GROUP, "engagement")
    assert (channel.group.n, channel.group_excluded_no_views) == (16, 1)


@pytest.mark.parametrize("metric", list(METRICS))
def test_topics_plus_noise_add_up_to_the_channel_row(metric: str) -> None:
    result = compare_topics(_channel(), n_permutations=N_PERM)

    rows = [r for r in result.rows if r.metric == metric]
    parts = sum(r.group.n for r in rows if r.kind in ("topic", "noise"))
    assert parts == _row(rows, CHANNEL_GROUP, metric).group.n
    for row in rows:
        if row.rest is not None:
            assert row.group.n + row.rest.n == _row(rows, CHANNEL_GROUP, metric).group.n


def test_topic_with_no_measurable_post_stays_out_of_the_holm_family() -> None:
    units = _channel() + [_unit("c0", "topic_c", views=0)]
    result = compare_topics(units, n_permutations=N_PERM)

    empty = _row(result.rows, "topic_c", "engagement")
    assert empty.group.n == 0
    assert empty.p_value is None and empty.p_value_holm is None
    assert result.holm_family_size == 2 * len(METRICS)  # topic_a, topic_b — không có topic_c


def test_nan_p_value_stays_out_of_the_holm_family() -> None:
    # topic 1 bài đo được → không có bản hoán vị → nhánh Mann-Whitney; share_rate toàn 0 ở cả 2 nhóm
    # → p = NaN. Phép so đó không vào họ (holm_adjust sẽ raise nếu lọt vào)
    units = _channel() + [_unit("solo", "topic_solo", likes=3)]
    result = compare_topics(units, n_permutations=N_PERM)

    solo = _row(result.rows, "topic_solo", "share_rate")
    assert solo.test_method == "mann_whitney"
    assert solo.p_value is not None and solo.p_value != solo.p_value  # NaN
    assert solo.p_value_holm is None
    tested = [r for r in result.rows if r.tested]
    defined = [r for r in tested if r.p_value is not None and r.p_value == r.p_value]
    assert result.holm_family_size == len(defined) < len(tested)


def test_holm_family_matches_the_method_report() -> None:
    # Cùng nhóm topic/phần còn lại → họ Holm của job (`compare_topics`) và của
    # `scripts/topic_method_report.py` (`holm_by_key`) cho cùng p Holm. Chỉ kiểm phần họ: cách
    # script tự dựng nhóm từ DB không được test này chạm (đã đối chiếu tay trên DB thật 2026-10-09:
    # lệch 0.0)
    from scripts.topic_method_report import TopicTest, holm_by_key

    units = _channel()
    result = compare_topics(units, n_permutations=N_PERM)
    tests: list[TopicTest] = []
    for metric, value_of in METRICS.items():
        for topic_id in ("topic_a", "topic_b"):
            measured = [
                (u.topic_id, u.insights)
                for u in units
                if u.insights is not None and u.insights.views > 0
            ]
            topic_values = [value_of(item) for tid, item in measured if tid == topic_id]
            rest_values = [value_of(item) for tid, item in measured if tid != topic_id]
            report_result = compare_groups(
                topic_values, rest_values, n_permutations=N_PERM, random_seed=0
            )
            tests.append(TopicTest(topic_id, metric, report_result, None))
    report_holm = holm_by_key(tests, "BM-perm")

    assert len(report_holm) == result.holm_family_size
    for (report_topic, report_metric), p_holm in report_holm.items():
        assert _row(result.rows, report_topic, report_metric).p_value_holm == p_holm


def test_same_units_in_any_order_give_identical_rows() -> None:
    units = _channel()
    first = compare_topics(units, n_permutations=N_PERM)
    second = compare_topics(list(reversed(units)), n_permutations=N_PERM)

    # so repr: share_rate toàn 0 trong fixture → p Mann-Whitney = NaN, mà NaN != NaN
    assert repr(first) == repr(second)
