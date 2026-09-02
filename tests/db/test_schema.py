from datetime import UTC, datetime
from pathlib import Path

from src.api.models import MediaType, ThreadsPost
from src.db.schema import (
    connect,
    create_schema,
    get_content_unit,
    get_post,
    get_post_topic_label,
    insert_insight_snapshot,
    latest_insight_snapshot,
    list_content_units,
    list_root_posts,
    snapshot_row_to_post_insights,
    update_content_unit_embedding_coords,
    update_content_unit_language,
    update_content_unit_text,
    upsert_content_unit,
    upsert_post,
    upsert_post_topic_label,
    upsert_topic,
)
from src.models.content_unit import ContentUnit
from src.models.insight_snapshot import InsightSnapshot


def _post(post_id: str) -> ThreadsPost:
    return ThreadsPost(
        id=post_id,
        timestamp=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
    )


def test_create_schema_is_idempotent(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)
    create_schema(conn)  # phải chạy lại được không lỗi (CREATE TABLE IF NOT EXISTS)
    conn.close()


def test_upsert_and_get_post_roundtrip(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)

    upsert_post(conn, _post("post-1"))
    conn.commit()

    row = get_post(conn, "post-1")
    assert row is not None
    assert row["id"] == "post-1"
    assert row["media_type"] == "TEXT_POST"
    conn.close()


def test_list_root_posts_excludes_replies(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)

    root = _post("root-1")
    reply = ThreadsPost(
        id="reply-1",
        timestamp=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
        is_reply=True,
    )
    upsert_post(conn, root)
    upsert_post(conn, reply)
    conn.commit()

    rows = list_root_posts(conn)

    assert [row["id"] for row in rows] == ["root-1"]
    conn.close()


def test_upsert_post_is_upsert_not_duplicate_insert(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)

    upsert_post(conn, _post("post-1"))
    updated = ThreadsPost(
        id="post-1",
        text="updated",
        timestamp=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
    )
    upsert_post(conn, updated)
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    assert count == 1
    row = get_post(conn, "post-1")
    assert row is not None
    assert row["text"] == "updated"
    conn.close()


def test_content_unit_insert_and_text_update_roundtrip(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)

    root = _post("root-1")
    upsert_post(conn, root)
    unit = ContentUnit(root=root, full_text="hello   world  https://a.example")
    upsert_content_unit(conn, unit)
    update_content_unit_text(
        conn, unit.id, raw_text=unit.full_text, normalized_text="hello world https://a.example"
    )
    conn.commit()

    row = get_content_unit(conn, "root-1")
    assert row is not None
    assert row["raw_text"] == "hello   world  https://a.example"
    assert row["normalized_text"] == "hello world https://a.example"

    all_units = list_content_units(conn)
    assert len(all_units) == 1
    conn.close()


def test_content_unit_embedding_coords_and_language_update(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)

    root = _post("root-1")
    upsert_post(conn, root)
    upsert_content_unit(conn, ContentUnit(root=root, full_text="hello"))
    update_content_unit_embedding_coords(conn, "root-1", x=1.0, y=2.0, z=3.0)
    update_content_unit_language(conn, "root-1", primary_language="vi", mix_score=0.2)
    conn.commit()

    row = get_content_unit(conn, "root-1")
    assert row is not None
    assert row["umap_x"] == 1.0
    assert row["umap_y"] == 2.0
    assert row["umap_z"] == 3.0
    assert row["language_primary"] == "vi"
    assert row["language_mix_score"] == 0.2
    conn.close()


def test_insight_snapshot_insert_and_latest(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)
    upsert_post(conn, _post("post-1"))

    insert_insight_snapshot(
        conn,
        InsightSnapshot(
            post_id="post-1",
            fetched_at=datetime(2026, 8, 30, 8, 0, tzinfo=UTC),
            views=1000,
            likes=10,
            replies=1,
            reposts=0,
            quotes=0,
        ),
    )
    insert_insight_snapshot(
        conn,
        InsightSnapshot(
            post_id="post-1",
            fetched_at=datetime(2026, 8, 30, 20, 0, tzinfo=UTC),
            views=1500,
            likes=20,
            replies=2,
            reposts=1,
            quotes=0,
        ),
    )
    conn.commit()

    latest = latest_insight_snapshot(conn, "post-1")
    assert latest is not None
    assert latest["views"] == 1500  # phải lấy snapshot mới nhất, không phải đầu tiên

    insights = snapshot_row_to_post_insights(latest)
    assert insights.post_id == "post-1"
    assert insights.views == 1500
    conn.close()


def test_latest_insight_snapshot_returns_none_when_no_snapshot(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)
    upsert_post(conn, _post("post-1"))
    conn.commit()

    assert latest_insight_snapshot(conn, "post-1") is None
    conn.close()


def test_topic_and_post_topic_label_roundtrip(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)
    upsert_post(conn, _post("post-1"))

    upsert_topic(
        conn,
        topic_id="cluster-0",
        label_en="Alternance search stories",
        description_en="Posts about finding an alternance placement in France.",
        method="cluster",
        centroid_embedding=[0.1, 0.2, 0.3],
    )
    upsert_post_topic_label(
        conn, post_id="post-1", topic_id="cluster-0", method="cluster", confidence=0.9
    )
    conn.commit()

    label = get_post_topic_label(conn, "post-1", method="cluster")
    assert label is not None
    assert label["topic_id"] == "cluster-0"
    assert label["confidence"] == 0.9
    conn.close()


def test_get_post_topic_label_returns_none_when_untagged(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)
    upsert_post(conn, _post("post-1"))
    conn.commit()

    assert get_post_topic_label(conn, "post-1", method="cluster") is None
    conn.close()
