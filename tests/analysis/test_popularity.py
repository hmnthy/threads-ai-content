from src.analysis.popularity import popularity_index
from src.api.models import PostInsights


def test_popularity_index_is_views() -> None:
    insights = PostInsights(post_id="1", views=1234, likes=10, replies=1, reposts=0, quotes=0)
    assert popularity_index(insights) == 1234


def test_popularity_index_zero_views() -> None:
    insights = PostInsights(post_id="1", views=0, likes=0, replies=0, reposts=0, quotes=0)
    assert popularity_index(insights) == 0
