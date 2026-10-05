from datetime import UTC, datetime

from src.api.models import MediaType, ThreadsPost
from src.processing.thread_reconstruction import assign_reply_roles, build_content_units


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


# --- phân vai reply (ADR-0004) -----------------------------------------------------


def _own_reply(
    post_id: str, root_id: str | None, replied_to: str | None, minute: int, text: str = ""
) -> ThreadsPost:
    return ThreadsPost(
        id=post_id,
        text=text or post_id,
        timestamp=datetime(2026, 8, 24, 10, minute, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
        is_reply=True,
        is_reply_owned_by_me=True,
        root_post={"id": root_id} if root_id else None,
        replied_to={"id": replied_to} if replied_to else None,
    )


def test_reply_roles_separate_continuation_answer_and_outbound() -> None:
    root = _root("r", "post")
    replies = [
        _own_reply("c1", "r", "r", 1),  # viết tiếp vào root
        _own_reply("c2", "r", "c1", 2),  # viết tiếp vào đoạn nối chuỗi trước
        _own_reply("a1", "r", "follower-comment", 3),  # trả lời follower
        _own_reply("a2", "r", "a1", 4),  # viết tiếp dưới câu trả lời follower của mình
        _own_reply("a3", "r", None, 5),  # bình luận gốc đã bị xoá → không chứng minh được
        _own_reply("o1", "someone-else-root", "someone-else-root", 6),  # bài người khác
        _own_reply("o2", None, None, 7),  # reply không có root_post
    ]
    roles = assign_reply_roles([root], replies)
    assert roles == {
        "c1": "self_continuation",
        "c2": "self_continuation",
        "a1": "author_answer",
        "a2": "author_answer",
        "a3": "author_answer",
        "o1": "outbound",
        "o2": "outbound",
    }


def test_answers_to_followers_stay_out_of_full_text() -> None:
    # Ví dụ thật (bài "rau muống" 2026-08-18): 2 đoạn nối chuỗi + 6 câu trả lời follower
    root = _root("r", "dĩa rau muống")
    replies = [
        _own_reply("c1", "r", "r", 1, "rau 6€/kg"),
        _own_reply("c2", "r", "c1", 2, "bí đao bự"),
        _own_reply("a1", "r", "f1", 3, "chị này bán rau hot lắm"),
    ]
    [unit] = build_content_units([root], replies)
    assert [c.id for c in unit.continuations] == ["c1", "c2"]
    assert unit.full_text == "dĩa rau muống rau 6€/kg bí đao bự"


def test_continuation_after_an_answer_still_chains_from_its_own_parent() -> None:
    # Thứ tự thời gian xen kẽ: trả lời follower xảy ra giữa 2 đoạn nối chuỗi
    root = _root("r", "p1")
    replies = [
        _own_reply("c1", "r", "r", 1, "p2"),
        _own_reply("a1", "r", "f1", 2, "answer"),
        _own_reply("c2", "r", "c1", 3, "p3"),
    ]
    [unit] = build_content_units([root], replies)
    assert unit.full_text == "p1 p2 p3"


def test_text_attachment_is_appended_to_full_text() -> None:
    # Shape thật của API: {"plaintext": "..."} — validator làm phẳng thành str
    root = ThreadsPost.model_validate(
        {
            "id": "r",
            "text": "short intro",
            "timestamp": "2026-08-24T09:00:00+00:00",
            "media_type": "TEXT_POST",
            "text_attachment": {"plaintext": "long body"},
        }
    )
    [unit] = build_content_units([root], [])
    assert unit.text_attachment == "long body"
    assert unit.full_text == "short intro long body"


def test_roles_do_not_depend_on_timestamps_or_input_order() -> None:
    # Composer nhiều phần: con trùng giờ cha, thậm chí sớm hơn cha (data thật 2026-10-01)
    root = _root("r", "p1")
    c1 = _own_reply("c1", "r", "r", 5, "p2")
    c2 = _own_reply("c2", "r", "c1", 5, "p3")  # trùng giây với cha
    c3 = _own_reply("c3", "r", "c2", 4, "p4")  # sớm hơn cha 1 phút
    answer = _own_reply("a1", "r", "f1", 6, "answer")
    under_answer = _own_reply("a2", "r", "a1", 3, "more answer")  # dây chuyền dưới câu trả lời
    replies = [c1, c2, c3, answer, under_answer]
    expected = {
        "c1": "self_continuation",
        "c2": "self_continuation",
        "c3": "self_continuation",
        "a1": "author_answer",
        "a2": "author_answer",
    }
    assert assign_reply_roles([root], replies) == expected
    assert assign_reply_roles([root], list(reversed(replies))) == expected
    [unit] = build_content_units([root], list(reversed(replies)))
    assert unit.full_text == "p1 p2 p3 p4"  # thứ tự đọc theo cây, không theo giờ


def test_reply_cycle_does_not_loop_forever() -> None:
    root = _root("r", "p")
    x = _own_reply("x", "r", "y", 1)
    y = _own_reply("y", "r", "x", 2)
    assert assign_reply_roles([root], [x, y]) == {"x": "author_answer", "y": "author_answer"}


def test_thread_order_reads_first_branch_fully_before_its_sibling() -> None:
    # 2 đoạn cùng trả lời root (anh em): nhánh sớm hơn được đọc trọn trước
    root = _root("r", "p0")
    replies = [
        _own_reply("b1", "r", "r", 2, "B1"),
        _own_reply("a1", "r", "r", 1, "A1"),
        _own_reply("a2", "r", "a1", 3, "A2"),
    ]
    [unit] = build_content_units([root], replies)
    assert unit.full_text == "p0 A1 A2 B1"
