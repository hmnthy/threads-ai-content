from src.api.models import MediaType, PostInsights, ThreadsPost, UserInfo


def test_threads_post_parses_minimal_payload() -> None:
    post = ThreadsPost.model_validate(
        {
            "id": "123",
            "timestamp": "2026-08-28T10:00:00+0000",
            "media_type": "TEXT_POST",
        }
    )
    assert post.id == "123"
    assert post.media_type == MediaType.TEXT_POST
    assert post.children == []
    assert post.text is None


def test_threads_post_flattens_children_edge_shape_from_real_api() -> None:
    # Confirmed against a live API response on 2026-08-28: children comes back as an
    # edge (`{"data": [{"id": ...}]}`), not a flat list of ids.
    post = ThreadsPost.model_validate(
        {
            "id": "123",
            "timestamp": "2026-08-28T10:00:00+0000",
            "media_type": "CAROUSEL_ALBUM",
            "children": {"data": [{"id": "18015467"}, {"id": "18114588592987565"}]},
        }
    )
    assert post.children == ["18015467", "18114588592987565"]


def test_user_info_requires_id_and_username() -> None:
    info = UserInfo.model_validate({"id": "1", "username": "thydilammuon"})
    assert info.username == "thydilammuon"


def test_post_insights_engagement_rate_formula() -> None:
    insights = PostInsights(post_id="1", views=1000, likes=80, replies=10, reposts=5, quotes=2)
    # (likes + replies + reposts) / views * 100, per docs/claude/data-model.md's decided formula
    assert insights.engagement_rate == (80 + 10 + 5) / 1000 * 100


def test_post_insights_engagement_rate_zero_views_does_not_divide_by_zero() -> None:
    insights = PostInsights(post_id="1", views=0, likes=5, replies=0, reposts=0, quotes=0)
    assert insights.engagement_rate == 0.0
