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


def test_threads_post_thread_reconstruction_fields_default_safely() -> None:
    # A root post (top of the channel feed) has none of these fields set by the API.
    post = ThreadsPost.model_validate(
        {
            "id": "123",
            "timestamp": "2026-08-28T10:00:00+0000",
            "media_type": "TEXT_POST",
        }
    )
    assert post.root_post is None
    assert post.replied_to is None
    assert post.root_post_id is None
    assert post.replied_to_id is None
    assert post.is_reply is False
    assert post.is_reply_owned_by_me is False


def test_threads_post_root_post_and_replied_to_ids_from_real_api_shape() -> None:
    # Confirmed live 2026-08-30 (limit=20 on /replies): root_post/replied_to come back
    # as an edge {"id": "..."}, same shape as quoted_post/reposted_post.
    post = ThreadsPost.model_validate(
        {
            "id": "reply-1",
            "timestamp": "2026-08-28T10:00:00+0000",
            "media_type": "TEXT_POST",
            "root_post": {"id": "root-1"},
            "replied_to": {"id": "parent-1"},
            "is_reply": True,
            "is_reply_owned_by_me": True,
        }
    )
    assert post.root_post_id == "root-1"
    assert post.replied_to_id == "parent-1"
    assert post.is_reply is True
    assert post.is_reply_owned_by_me is True


def test_threads_post_flattens_text_attachment_edge_shape_from_real_api() -> None:
    # Verify live 2026-08-31 (đợt fetch thật 140 posts + 1,285 replies): NGƯỢC với
    # ghi chú "0/100 item có data" trong data-model.md (viết từ mẫu nhỏ 2026-08-30) —
    # trên toàn bộ dữ liệu thật, text_attachment CÓ được dùng, và trả về dạng
    # {"plaintext": "..."}, không phải string phẳng.
    post = ThreadsPost.model_validate(
        {
            "id": "123",
            "timestamp": "2026-08-28T10:00:00+0000",
            "media_type": "TEXT_POST",
            "text_attachment": {"plaintext": "Nhưng trời ơi tận tình luôn."},
        }
    )
    assert post.text_attachment == "Nhưng trời ơi tận tình luôn."


def test_threads_post_text_attachment_still_accepts_plain_string() -> None:
    post = ThreadsPost.model_validate(
        {
            "id": "123",
            "timestamp": "2026-08-28T10:00:00+0000",
            "media_type": "TEXT_POST",
            "text_attachment": "already a plain string",
        }
    )
    assert post.text_attachment == "already a plain string"


def test_user_info_requires_id_and_username() -> None:
    info = UserInfo.model_validate({"id": "1", "username": "thydilammuon"})
    assert info.username == "thydilammuon"


def test_post_insights_engagement_rate_formula() -> None:
    insights = PostInsights(post_id="1", views=1000, likes=80, replies=10, reposts=5, quotes=2)
    # (likes + replies + reposts + quotes) / views * 100 — data-model.md "Metric Architecture"
    assert insights.engagement_rate == (80 + 10 + 5 + 2) / 1000 * 100


def test_post_insights_engagement_rate_zero_views_does_not_divide_by_zero() -> None:
    insights = PostInsights(post_id="1", views=0, likes=5, replies=0, reposts=0, quotes=0)
    assert insights.engagement_rate == 0.0
