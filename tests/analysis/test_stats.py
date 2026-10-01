from datetime import UTC, datetime

from src.analysis.stats import MIN_N_PER_BUCKET, distribution_stats, split_measurable, window_stats
from src.api.models import MediaType, PostInsights, ThreadsPost


def _insights(post_id: str, *, views: int, likes: int) -> PostInsights:
    return PostInsights(post_id=post_id, views=views, likes=likes, replies=0, reposts=0, quotes=0)


def test_distribution_stats_empty_list_is_insufficient() -> None:
    stats = distribution_stats([])
    assert stats == distribution_stats([])
    assert stats.n == 0
    assert stats.median == 0.0
    assert stats.mean == 0.0
    assert stats.insufficient_data is True


def test_distribution_stats_single_value_has_zero_spread() -> None:
    stats = distribution_stats([42.0])
    assert stats.n == 1
    assert stats.median == 42.0
    assert stats.mean == 42.0
    assert stats.iqr_low == stats.iqr_high == 42.0
    assert stats.insufficient_data is True  # n=1 < MIN_N_PER_BUCKET


def test_distribution_stats_median_resists_outlier_unlike_mean() -> None:
    values = [2.0, 2.0, 2.0, 2.0, 500.0]
    stats = distribution_stats(values)
    assert stats.median == 2.0
    assert stats.mean == 101.6
    assert stats.n == 5
    assert stats.insufficient_data is False  # n == MIN_N_PER_BUCKET


def test_distribution_stats_insufficient_flag_matches_shared_threshold() -> None:
    just_below = distribution_stats([1.0] * (MIN_N_PER_BUCKET - 1))
    just_at = distribution_stats([1.0] * MIN_N_PER_BUCKET)
    assert just_below.insufficient_data is True
    assert just_at.insufficient_data is False


def test_window_stats_applies_metric_fn_per_post_before_pooling() -> None:
    insights = [
        _insights("1", views=1000, likes=10),  # 1%
        _insights("2", views=1000, likes=20),  # 2%
        _insights("3", views=1000, likes=30),  # 3%
    ]
    stats = window_stats(insights, lambda item: item.engagement_rate)
    assert stats.median == 2.0
    assert stats.mean == 2.0
    assert stats.n == 3


def test_window_stats_is_not_a_pooled_ratio() -> None:
    # 1 post với 1 view (engagement_rate ảo cao) không được kéo lệch median như 1
    # pooled ratio Σinteractions/Σviews sẽ làm — đây là điểm khác biệt cốt lõi với
    # cách mockup UI tự tính (xem docstring src/analysis/stats.py).
    insights = [
        _insights("tiny", views=1, likes=1),  # 100% rate nhưng views quá nhỏ
        _insights("2", views=1000, likes=20),  # 2%
        _insights("3", views=1000, likes=20),  # 2%
    ]
    stats = window_stats(insights, lambda item: item.engagement_rate)
    assert stats.median == 2.0  # không bị "tiny" kéo lệch
    assert stats.mean != stats.median  # mean vẫn bị kéo — 2 số nên đi cùng nhau


def _post(post_id: str) -> ThreadsPost:
    return ThreadsPost(
        id=post_id, timestamp=datetime(2026, 2, 1, tzinfo=UTC), media_type=MediaType.TEXT_POST
    )


def test_split_measurable_drops_zero_view_posts_and_counts_them() -> None:
    # ADR-0011: views = 0 là insight thiếu — không được thành engagement 0% trong phân phối
    posts = [_post("a"), _post("b"), _post("c")]
    insights = [
        _insights("a", views=100, likes=5),
        _insights("b", views=0, likes=0),
        _insights("c", views=200, likes=4),
    ]
    kept_posts, kept_insights, excluded = split_measurable(posts, insights)
    assert [p.id for p in kept_posts] == ["a", "c"]
    assert [i.post_id for i in kept_insights] == ["a", "c"]
    assert excluded == 1
    # Không loại thì median bị số 0 giả kéo xuống
    with_zero = window_stats(insights, lambda i: i.engagement_rate)
    without = window_stats(kept_insights, lambda i: i.engagement_rate)
    assert with_zero.median == 2.0
    assert without.median == 3.5


def test_split_measurable_ignores_posts_without_insight() -> None:
    kept_posts, kept_insights, excluded = split_measurable(
        [_post("a"), _post("x")], [_insights("a", views=10, likes=1)]
    )
    assert [p.id for p in kept_posts] == ["a"]
    assert len(kept_insights) == 1
    assert excluded == 0
