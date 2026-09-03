from src.analysis.stats import MIN_N_PER_BUCKET, distribution_stats, window_stats
from src.api.models import PostInsights


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
