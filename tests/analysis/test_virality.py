from src.analysis.virality import channel_virality_p90, is_viral, virality_index
from src.api.models import PostInsights


def test_virality_index_formula() -> None:
    insights = PostInsights(post_id="1", views=1000, likes=80, replies=10, reposts=5, quotes=2)
    assert virality_index(insights) == (5 + 2) / 1000 * 100


def test_virality_index_zero_views_does_not_divide_by_zero() -> None:
    insights = PostInsights(post_id="1", views=0, likes=0, replies=0, reposts=1, quotes=1)
    assert virality_index(insights) == 0.0


def test_virality_index_ignores_likes_and_replies() -> None:
    # Không được trộn engagement thường vào virality — chỉ đo redistribution (reposts+quotes).
    high_likes = PostInsights(post_id="1", views=1000, likes=500, replies=200, reposts=0, quotes=0)
    assert virality_index(high_likes) == 0.0


def _insights(post_id: str, *, views: int, reposts: int, quotes: int) -> PostInsights:
    return PostInsights(
        post_id=post_id, views=views, likes=0, replies=0, reposts=reposts, quotes=quotes
    )


def test_channel_virality_p90_empty_list_returns_zero() -> None:
    assert channel_virality_p90([]) == 0.0


def test_channel_virality_p90_is_at_least_the_9th_highest_of_10_posts() -> None:
    # 10 posts với virality_index tăng dần 0%, 1%, ..., 9% -> P90 phải nằm giữa
    # giá trị thứ 9 (8%) và cao nhất (9%).
    insights = [
        _insights(str(i), views=100, reposts=i, quotes=0)  # virality = i%
        for i in range(10)
    ]
    p90 = channel_virality_p90(insights)
    assert 8.0 <= p90 <= 9.0


def test_is_viral_true_when_above_channel_p90_and_meets_floor() -> None:
    assert is_viral(virality_index_value=9.5, channel_p90=8.0, views=500, floor=100) is True


def test_is_viral_false_when_below_channel_p90() -> None:
    assert is_viral(virality_index_value=5.0, channel_p90=8.0, views=500, floor=100) is False


def test_is_viral_false_when_below_views_floor_even_if_above_p90() -> None:
    # Post đạt percentile cao nhưng views quá ít (ăn may vì mẫu bé) -> không viral.
    assert is_viral(virality_index_value=9.5, channel_p90=8.0, views=50, floor=100) is False


def test_is_viral_boundary_is_inclusive_for_floor_and_exclusive_for_p90() -> None:
    # views == floor -> đạt điều kiện floor (>=); virality == p90 -> KHÔNG đạt (>).
    assert is_viral(virality_index_value=8.0, channel_p90=8.0, views=100, floor=100) is False
    assert is_viral(virality_index_value=8.01, channel_p90=8.0, views=100, floor=100) is True
