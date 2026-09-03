from __future__ import annotations

from datetime import UTC, datetime

from src.analysis.topic_affinity import (
    compare_virality_with_without_author_reply,
    is_author_reply_event,
)
from src.api.models import MediaType, ThreadsPost
from src.models.content_unit import ContentUnit

TS = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)


def _post(post_id: str, *, is_reply_owned_by_me: bool = False) -> ThreadsPost:
    return ThreadsPost(
        id=post_id,
        timestamp=TS,
        media_type=MediaType.TEXT_POST,
        is_reply=is_reply_owned_by_me,
        is_reply_owned_by_me=is_reply_owned_by_me,
    )


def test_is_author_reply_event_false_when_not_owned_by_author() -> None:
    root = _post("root-1")
    unit = ContentUnit(root=root, continuations=[], full_text="root")
    audience_reply = _post("audience-1", is_reply_owned_by_me=False)

    assert is_author_reply_event(audience_reply, unit) is False


def test_is_author_reply_event_false_for_self_continuation() -> None:
    root = _post("root-1")
    continuation = _post("continuation-1", is_reply_owned_by_me=True)
    unit = ContentUnit(root=root, continuations=[continuation], full_text="root continuation")

    assert is_author_reply_event(continuation, unit) is False


def test_is_author_reply_event_true_when_author_replies_into_audience_conversation() -> None:
    root = _post("root-1")
    continuation = _post("continuation-1", is_reply_owned_by_me=True)
    unit = ContentUnit(root=root, continuations=[continuation], full_text="root continuation")
    # Same is_reply_owned_by_me=True as the continuation, but NOT one of the
    # unit's own continuations -> this is the author replying into audience talk.
    reply_into_audience_thread = _post("author-reply-to-audience", is_reply_owned_by_me=True)

    assert is_author_reply_event(reply_into_audience_thread, unit) is True


def test_compare_virality_with_without_author_reply_delegates_to_compare_groups() -> None:
    posts_with_reply = [5.0, 6.0, 7.0, 8.0, 9.0]
    posts_without_reply = [1.0, 1.5, 2.0, 2.5, 3.0]

    result = compare_virality_with_without_author_reply(posts_with_reply, posts_without_reply)

    assert result.n_a == 5
    assert result.n_b == 5
    assert result.median_a == 7.0
    assert result.median_b == 2.0
    assert result.p_value is not None
