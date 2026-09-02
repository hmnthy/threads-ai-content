from src.analysis.virality import virality_index
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
