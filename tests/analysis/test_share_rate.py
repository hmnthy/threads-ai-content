from src.analysis.share_rate import share_rate
from src.api.models import PostInsights


def test_share_rate_formula() -> None:
    insights = PostInsights(post_id="1", views=1000, likes=80, replies=10, reposts=5, quotes=2)
    assert share_rate(insights) == (5 + 2) / 1000 * 100


def test_share_rate_zero_views_does_not_divide_by_zero() -> None:
    insights = PostInsights(post_id="1", views=0, likes=0, replies=0, reposts=1, quotes=1)
    assert share_rate(insights) == 0.0


def test_share_rate_ignores_likes_and_replies() -> None:
    # Không được trộn engagement thường vào share_rate — chỉ đo đăng lại / trích dẫn.
    high_likes = PostInsights(post_id="1", views=1000, likes=500, replies=200, reposts=0, quotes=0)
    assert share_rate(high_likes) == 0.0
