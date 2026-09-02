from datetime import UTC, datetime

from src.api.models import MediaType, ThreadsPost
from src.processing.thread_reconstruction import build_content_units


def _root(post_id: str, text: str) -> ThreadsPost:
    return ThreadsPost(
        id=post_id,
        text=text,
        timestamp=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
    )


def _reply(
    post_id: str, text: str, root_id: str, ts: datetime, *, owned_by_me: bool = True
) -> ThreadsPost:
    return ThreadsPost(
        id=post_id,
        text=text,
        timestamp=ts,
        media_type=MediaType.TEXT_POST,
        is_reply=True,
        is_reply_owned_by_me=owned_by_me,
        root_post={"id": root_id},
        replied_to={"id": root_id},
    )


def test_build_content_units_single_post_no_continuations() -> None:
    root = _root("1", "hello")
    units = build_content_units([root], [])
    assert len(units) == 1
    assert units[0].id == "1"
    assert units[0].continuations == []
    assert units[0].full_text == "hello"
    assert units[0].is_multi_post is False


def test_build_content_units_chains_self_replies_sorted_by_timestamp() -> None:
    root = _root("1", "part 1")
    c1 = _reply("2", "part 2", "1", datetime(2026, 8, 24, 9, 5, tzinfo=UTC))
    c2 = _reply("3", "part 3", "1", datetime(2026, 8, 24, 9, 10, tzinfo=UTC))

    # Truyền vào theo thứ tự ngược (get_replies() không đảm bảo thứ tự) — phải tự sort.
    units = build_content_units([root], [c2, c1])

    assert len(units) == 1
    unit = units[0]
    assert [c.id for c in unit.continuations] == ["2", "3"]
    assert unit.full_text == "part 1 part 2 part 3"
    assert unit.is_multi_post is True


def test_build_content_units_excludes_audience_replies() -> None:
    root = _root("1", "hello")
    audience_reply = _reply(
        "2", "not mine", "1", datetime(2026, 8, 24, 9, 5, tzinfo=UTC), owned_by_me=False
    )

    units = build_content_units([root], [audience_reply])

    assert units[0].continuations == []
    assert units[0].full_text == "hello"  # audience reply KHÔNG gộp vào full_text


def test_build_content_units_multiple_roots_stay_independent() -> None:
    root1 = _root("1", "root one")
    root2 = _root("2", "root two")
    continuation_of_root2 = _reply("3", "continued", "2", datetime(2026, 8, 24, 9, 5, tzinfo=UTC))

    units = build_content_units([root1, root2], [continuation_of_root2])
    by_id = {unit.id: unit for unit in units}

    assert by_id["1"].continuations == []
    assert [c.id for c in by_id["2"].continuations] == ["3"]


def test_build_content_units_media_collects_non_text_posts_in_chain() -> None:
    root = ThreadsPost(
        id="1", timestamp=datetime(2026, 8, 24, 9, 0, tzinfo=UTC), media_type=MediaType.IMAGE
    )
    units = build_content_units([root], [])
    assert [post.id for post in units[0].media] == ["1"]
