from datetime import UTC, datetime
from pathlib import Path

from src.api.models import MediaType, ThreadsPost
from src.db.schema import (
    connect,
    count_reply_roles,
    create_schema,
    get_content_unit,
    upsert_content_unit,
    upsert_post,
)
from src.models.content_unit import ContentUnit
from src.pipeline.ingest import rebuild_content_units


def _post(
    post_id: str, minute: int, *, root: str | None = None, to: str | None = None
) -> ThreadsPost:
    return ThreadsPost(
        id=post_id,
        text=post_id,
        timestamp=datetime(2026, 8, 18, 17, minute, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
        is_reply=root is not None or to is not None,
        is_reply_owned_by_me=root is not None or to is not None,
        root_post={"id": root} if root else None,
        replied_to={"id": to} if to else None,
    )


def test_rebuild_content_units_drops_follower_answers_from_stored_units(tmp_path: Path) -> None:
    conn = connect(tmp_path / "rebuild.db")
    create_schema(conn)
    root = _post("root", 0)
    c1 = _post("c1", 1, root="root", to="root")
    answer = _post("a1", 2, root="root", to="follower-comment")
    outbound = _post("o1", 3)
    outbound = outbound.model_copy(update={"is_reply": True, "is_reply_owned_by_me": True})
    for post in (root, c1, answer, outbound):
        upsert_post(conn, post)
    # Trạng thái cũ (lỗi D0): câu trả lời follower đã bị gộp vào content unit
    upsert_content_unit(
        conn, ContentUnit(root=root, continuations=[c1, answer], full_text="root c1 a1")
    )
    conn.commit()

    counts = rebuild_content_units(conn)

    assert counts == {
        "content_units": 1,
        "self_continuation": 1,
        "author_answer": 1,
        "outbound": 1,
    }
    assert count_reply_roles(conn) == {"self_continuation": 1, "author_answer": 1, "outbound": 1}
    unit = get_content_unit(conn, "root")
    assert unit is not None
    assert unit["full_text"] == "root c1"
    assert unit["continuation_ids_json"] == '["c1"]'
