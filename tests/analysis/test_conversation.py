from src.analysis.conversation import conversation_rate
from src.api.models import PostInsights


def test_conversation_rate_formula() -> None:
    insights = PostInsights(post_id="1", views=1000, likes=80, replies=15, reposts=5, quotes=2)
    assert conversation_rate(insights) == 15 / 1000 * 100


def test_conversation_rate_zero_views_does_not_divide_by_zero() -> None:
    insights = PostInsights(post_id="1", views=0, likes=0, replies=3, reposts=0, quotes=0)
    assert conversation_rate(insights) == 0.0
