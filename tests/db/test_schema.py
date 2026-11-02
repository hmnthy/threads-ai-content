import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import src.db.schema as schema_module
from src.api.models import MediaType, ThreadsPost
from src.db.schema import (
    connect,
    content_hash,
    count_reply_roles,
    create_schema,
    get_content_unit,
    get_post,
    get_post_topic_label,
    insert_cluster_run,
    insert_insight_snapshot,
    latest_cluster_run,
    latest_insight_snapshot,
    list_content_units,
    list_daily_views,
    list_root_posts,
    list_root_posts_in_range,
    load_embeddings,
    snapshot_row_to_post_insights,
    update_content_unit_embedding_coords,
    update_content_unit_language,
    update_content_unit_text,
    update_reply_roles,
    upsert_content_unit,
    upsert_daily_views,
    upsert_embedding,
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


def test_list_root_posts_in_range_filters_inclusive_by_paris_calendar_day(tmp_path: Path) -> None:
    # ADR-0034: ngày đăng = ngày giờ Paris (tháng 8 = UTC+2). Hai bài biên nằm ở ngày UTC khác
    # ngày Paris — bộ lọc cắt `timestamp[:10]` (ngày UTC) sẽ lấy sai cả hai
    conn = connect(tmp_path / "test.db")
    create_schema(conn)

    def _post_at(post_id: str, ts: datetime) -> ThreadsPost:
        return ThreadsPost(id=post_id, timestamp=ts, media_type=MediaType.TEXT_POST)

    # 23:59 Paris ngày 9
    upsert_post(conn, _post_at("before", datetime(2026, 8, 9, 21, 59, tzinfo=UTC)))
    # 00:00 Paris ngày 10 (UTC vẫn là ngày 9)
    upsert_post(conn, _post_at("start-boundary", datetime(2026, 8, 9, 22, 0, tzinfo=UTC)))
    upsert_post(conn, _post_at("inside", datetime(2026, 8, 15, 12, 0, tzinfo=UTC)))
    # 23:59 Paris ngày 20
    upsert_post(conn, _post_at("end-boundary", datetime(2026, 8, 20, 21, 59, tzinfo=UTC)))
    # 00:00 Paris ngày 21 (UTC vẫn là ngày 20)
    upsert_post(conn, _post_at("after", datetime(2026, 8, 20, 22, 0, tzinfo=UTC)))
    conn.commit()

    rows = list_root_posts_in_range(conn, "2026-08-10", "2026-08-20")

    assert {row["id"] for row in rows} == {"start-boundary", "inside", "end-boundary"}
    conn.close()


def test_list_root_posts_in_range_excludes_replies(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)

    upsert_post(conn, _post("root-1"))
    upsert_post(
        conn,
        ThreadsPost(
            id="reply-1",
            timestamp=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
            media_type=MediaType.TEXT_POST,
            is_reply=True,
        ),
    )
    conn.commit()

    rows = list_root_posts_in_range(conn, "2026-08-01", "2026-08-31")

    assert [row["id"] for row in rows] == ["root-1"]
    conn.close()


def test_upsert_daily_views_overwrites_on_conflict(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)

    upsert_daily_views(conn, date="2026-08-10", views=100, fetched_at="2026-08-11T00:00:00+00:00")
    upsert_daily_views(conn, date="2026-08-10", views=150, fetched_at="2026-08-12T00:00:00+00:00")
    conn.commit()

    rows = list_daily_views(conn)
    assert len(rows) == 1
    assert rows[0]["views"] == 150  # backfill trễ ghi đè, không insert trùng


def test_list_daily_views_orders_by_date_and_filters_range(tmp_path: Path) -> None:
    conn = connect(tmp_path / "test.db")
    create_schema(conn)

    for day, views in [("2026-08-12", 3), ("2026-08-10", 1), ("2026-08-11", 2)]:
        upsert_daily_views(conn, date=day, views=views, fetched_at="2026-08-13T00:00:00+00:00")
    conn.commit()

    all_rows = list_daily_views(conn)
    assert [row["date"] for row in all_rows] == ["2026-08-10", "2026-08-11", "2026-08-12"]

    ranged = list_daily_views(conn, "2026-08-11", "2026-08-11")
    assert [row["date"] for row in ranged] == ["2026-08-11"]
    conn.close()


# --- migration + bảng mới (ADR-0004) ------------------------------------------------

_OLD_TOPIC_TABLES = """
CREATE TABLE topics (
    id TEXT PRIMARY KEY,
    label_en TEXT NOT NULL,
    description_en TEXT,
    method TEXT NOT NULL CHECK (method IN ('fixed', 'cluster')),
    centroid_embedding_json TEXT
);
CREATE TABLE post_topic_labels (
    post_id TEXT NOT NULL REFERENCES posts(id),
    topic_id TEXT NOT NULL REFERENCES topics(id),
    method TEXT NOT NULL CHECK (method IN ('fixed', 'cluster')),
    confidence REAL,
    PRIMARY KEY (post_id, method)
);
CREATE TABLE posts (
    id TEXT PRIMARY KEY, text TEXT, timestamp TEXT NOT NULL, media_type TEXT NOT NULL,
    permalink TEXT, is_reply INTEGER NOT NULL DEFAULT 0,
    is_reply_owned_by_me INTEGER NOT NULL DEFAULT 0, has_replies INTEGER NOT NULL DEFAULT 0,
    root_post_id TEXT, replied_to_id TEXT, raw_json TEXT NOT NULL
);
"""


def test_migration_upgrades_old_db_and_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "old.db"
    raw = sqlite3.connect(db_path)
    raw.executescript(_OLD_TOPIC_TABLES)
    raw.execute(
        "INSERT INTO posts (id, timestamp, media_type, raw_json) "
        "VALUES ('p1', 't', 'TEXT_POST', '{}')"
    )
    raw.execute("INSERT INTO topics VALUES ('cluster_0', 'A', NULL, 'cluster', NULL)")
    raw.execute("INSERT INTO topics VALUES ('fixed_cv', 'CV', NULL, 'fixed', NULL)")
    raw.execute("INSERT INTO post_topic_labels VALUES ('p1', 'cluster_0', 'cluster', NULL)")
    raw.execute("INSERT INTO post_topic_labels VALUES ('p1', 'fixed_cv', 'fixed', NULL)")
    raw.commit()
    raw.close()

    conn = connect(db_path)
    create_schema(conn)
    create_schema(conn)  # chạy lại không lỗi, không nhân đôi

    # ADR-0018: id theo vị trí `cluster_N` được đổi thành id bền `topic_N`
    assert {r["id"] for r in conn.execute("SELECT id FROM topics")} == {"topic_0"}
    assert [r["method"] for r in conn.execute("SELECT method FROM post_topic_labels")] == [
        "cluster"
    ]
    post_cols = {r[1] for r in conn.execute("PRAGMA table_info(posts)")}
    topic_cols = {r[1] for r in conn.execute("PRAGMA table_info(topics)")}
    assert "reply_role" in post_cols
    assert {"keywords_json", "representative_ids_json"} <= topic_cols
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO topics (id, label_en, method) VALUES ('x', 'X', 'fixed')")
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_reply_roles_roundtrip(tmp_path: Path) -> None:
    conn = connect(tmp_path / "roles.db")
    create_schema(conn)
    upsert_post(conn, _post("root"))
    reply = ThreadsPost(
        id="r1",
        timestamp=datetime(2026, 8, 24, 9, 5, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
        is_reply=True,
        is_reply_owned_by_me=True,
    )
    upsert_post(conn, reply)
    update_reply_roles(conn, {"r1": "author_answer"})
    assert count_reply_roles(conn) == {"author_answer": 1}
    # upsert lại post (job cron) không xoá vai đã gán
    upsert_post(conn, reply)
    assert get_post(conn, "r1")["reply_role"] == "author_answer"  # type: ignore[index]


def test_embedding_roundtrip_and_content_hash(tmp_path: Path) -> None:
    conn = connect(tmp_path / "emb.db")
    create_schema(conn)
    vec = [0.25, -0.5, 1.0]
    upsert_embedding(
        conn,
        object_type="content_unit",
        object_id="u1",
        model_id="BAAI/bge-m3",
        text_hash=content_hash("xin chào"),
        vector=vec,
        created_at="2026-10-01T00:00:00+00:00",
    )
    stored = load_embeddings(conn, object_type="content_unit", model_id="BAAI/bge-m3")
    assert stored == {"u1": (content_hash("xin chào"), vec)}
    assert content_hash("xin chào") != content_hash("xin chao")


def test_cluster_run_insert_and_latest(tmp_path: Path) -> None:
    conn = connect(tmp_path / "runs.db")
    create_schema(conn)
    assert latest_cluster_run(conn) is None
    for n in (8, 9):
        insert_cluster_run(
            conn,
            run_at=f"2026-10-0{n - 7}T00:00:00+00:00",
            model_id="BAAI/bge-m3",
            params={"min_cluster_size": 4},
            n_units=142,
            n_clusters=n,
            noise_ratio=0.23,
            dbcv=0.2,
            ari_vs_previous=None,
            labels={"u1": 0},
        )
    latest = latest_cluster_run(conn)
    assert latest is not None
    assert latest["n_clusters"] == 9


def _old_db(path: Path) -> None:
    raw = sqlite3.connect(path)
    raw.executescript(_OLD_TOPIC_TABLES)
    raw.execute(
        "INSERT INTO posts (id, timestamp, media_type, raw_json) "
        "VALUES ('p1', 't', 'TEXT_POST', '{}')"
    )
    raw.execute("INSERT INTO topics VALUES ('cluster_0', 'A', NULL, 'cluster', NULL)")
    raw.execute("INSERT INTO post_topic_labels VALUES ('p1', 'cluster_0', 'cluster', NULL)")
    raw.commit()
    raw.close()


def test_migration_failure_rolls_back_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "old.db"
    _old_db(db_path)
    conn = connect(db_path)
    real_drop = "DROP TABLE topics_old"

    original = schema_module._in_one_transaction

    def failing(conn: sqlite3.Connection, statements: list[str]) -> None:
        # Hỏng ngay trước lệnh cuối — mô phỏng `database is locked` giữa chừng
        original(conn, [s if s != real_drop else "DROP TABLE no_such_table" for s in statements])

    monkeypatch.setattr(schema_module, "_in_one_transaction", failing)
    with pytest.raises(sqlite3.OperationalError):
        create_schema(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "topics_old" not in tables and "post_topic_labels_old" not in tables
    assert (
        "'fixed'"
        in conn.execute("SELECT sql FROM sqlite_master WHERE name = 'topics'").fetchone()[0]
    )

    monkeypatch.setattr(schema_module, "_in_one_transaction", original)
    create_schema(conn)  # chạy lại sau lỗi → thành công, dữ liệu còn nguyên
    assert [r[0] for r in conn.execute("SELECT id FROM topics")] == ["topic_0"]  # ADR-0018
    assert conn.execute("SELECT COUNT(*) FROM post_topic_labels").fetchone()[0] == 1


def test_migration_recovers_db_left_half_renamed_by_old_version(tmp_path: Path) -> None:
    # Trạng thái bản migration cũ (không nguyên tử) có thể để lại: đã đổi tên
    # post_topic_labels → _old rồi chết; lần sau SCHEMA_SQL tạo bảng mới rỗng.
    db_path = tmp_path / "half.db"
    _old_db(db_path)
    raw = sqlite3.connect(db_path)
    raw.execute("ALTER TABLE post_topic_labels RENAME TO post_topic_labels_old")
    raw.commit()
    raw.close()

    conn = connect(db_path)
    create_schema(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "post_topic_labels_old" not in tables
    assert conn.execute("SELECT topic_id FROM post_topic_labels").fetchone()[0] == "topic_0"
    assert (
        "'fixed'"
        not in conn.execute("SELECT sql FROM sqlite_master WHERE name = 'topics'").fetchone()[0]
    )


def test_connect_waits_for_another_writer_longer_than_the_sqlite_default(
    tmp_path: Path,
) -> None:
    # 2 cron chạy chồng lúc máy thức dậy: chờ khoá thay vì `database is locked` sau 5 giây
    conn = schema_module.connect(tmp_path / "t.db")
    busy_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    conn.close()
    assert busy_ms == schema_module.LOCK_WAIT_S * 1000
    assert busy_ms > 5_000


# --- ADR-0034: nhãn ngày chuỗi views ---------------------------------------------------------

# end_time thật (shape verify live 2026-11-01) quanh 2 lần đổi giờ của Pacific: "07:00Z" = nửa đêm
# giờ mùa hè, "08:00Z" = nửa đêm giờ mùa đông. Ngày đúng = ngày Pacific của chính end_time.
_DST_END_TIMES = [
    ("2025-07-22T07:00:00+0000", 32973, "2025-07-22"),
    ("2025-11-01T07:00:00+0000", 11, "2025-11-01"),
    ("2025-11-02T07:00:00+0000", 12, "2025-11-02"),  # ngày Pacific trở về giờ mùa đông
    ("2025-11-03T08:00:00+0000", 13, "2025-11-03"),
    ("2026-01-15T08:00:00+0000", 14, "2026-01-15"),
    ("2026-03-07T08:00:00+0000", 15, "2026-03-07"),
    ("2026-03-08T08:00:00+0000", 16, "2026-03-08"),  # ngày Pacific sang giờ mùa hè
    ("2026-03-09T07:00:00+0000", 17, "2026-03-09"),
    ("2026-03-10T07:00:00+0000", 18, "2026-03-10"),
]


def _old_label(end_time: str) -> str:
    """Quy ước cũ (trước ADR-0034, `src/api/endpoints.py`): lùi 1 ngày chỉ khi giờ là "07"."""
    day = datetime.strptime(end_time[:10], "%Y-%m-%d").date()
    # consistency: allow ADR0034-old-day-label — dựng lại dữ liệu theo quy ước cũ để test migration
    return (day - timedelta(days=1) if end_time[11:13] == "07" else day).isoformat()


def _db_with_old_daily_view_labels(db_path: Path) -> sqlite3.Connection:
    conn = connect(db_path)
    create_schema(conn)
    conn.execute("DELETE FROM data_migrations")  # DB trước bản này: chưa có dấu
    for end_time, views, _ in _DST_END_TIMES:  # thứ tự như API trả: điểm sau ghi đè điểm trước
        upsert_daily_views(conn, date=_old_label(end_time), views=views, fetched_at="x")
    conn.commit()
    return conn


def _daily(conn: sqlite3.Connection) -> dict[str, int]:
    return {row["date"]: row["views"] for row in list_daily_views(conn)}


def test_old_labels_fixture_reproduces_the_bug(tmp_path: Path) -> None:
    # Dữ liệu test chạm đúng lỗi: ngày mùa hè sớm 1 ngày, 1 ngày trống, 1 ngày bị ghi đè
    conn = _db_with_old_daily_view_labels(tmp_path / "t.db")
    old = _daily(conn)
    assert old["2025-07-21"] == 32973
    assert "2025-11-02" not in old
    assert old["2026-03-08"] == 17  # giá trị của 03-09 đè lên 03-08
    conn.close()


def test_daily_views_relabel_migration_moves_rows_to_their_pacific_day(tmp_path: Path) -> None:
    conn = _db_with_old_daily_view_labels(tmp_path / "t.db")

    create_schema(conn)

    truth = {day: views for _, views, day in _DST_END_TIMES}
    # Ngày sang giờ mùa hè (03-08) đã mất ở quy ước cũ → trống, lần tải lại REFETCH lấp
    del truth["2026-03-08"]
    assert _daily(conn) == truth
    assert schema_module.migration_applied(conn, schema_module.DAILY_VIEWS_RELABEL_MIGRATION)
    conn.close()


def test_daily_views_relabel_migration_runs_once(tmp_path: Path) -> None:
    conn = _db_with_old_daily_view_labels(tmp_path / "t.db")
    create_schema(conn)
    once = _daily(conn)

    create_schema(conn)  # job cron gọi mỗi lần chạy
    schema_module._relabel_daily_views_to_meta_day(conn)  # gọi thẳng: kiểm dấu trong transaction

    assert _daily(conn) == once
    conn.close()


def test_daily_views_relabel_migration_on_fresh_db_only_sets_the_marker(tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    create_schema(conn)
    assert list_daily_views(conn) == []
    assert schema_module.migration_applied(conn, schema_module.DAILY_VIEWS_RELABEL_MIGRATION)
    # Dòng ghi theo quy ước mới sau đó không bị dời ở lần create_schema kế tiếp
    upsert_daily_views(conn, date="2026-07-01", views=5, fetched_at="x")
    conn.commit()
    create_schema(conn)
    assert _daily(conn) == {"2026-07-01": 5}
    conn.close()


def test_daily_views_relabel_migration_failure_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = _db_with_old_daily_view_labels(tmp_path / "t.db")
    before = _daily(conn)

    def _boom(_day: object) -> bool:
        raise RuntimeError("boom")

    monkeypatch.setattr(schema_module, "is_meta_summer_time", _boom)
    with pytest.raises(RuntimeError, match="boom"):
        create_schema(conn)

    assert not conn.in_transaction
    assert _daily(conn) == before
    assert not schema_module.migration_applied(conn, schema_module.DAILY_VIEWS_RELABEL_MIGRATION)
    conn.close()


def test_daily_views_relabel_migration_waits_for_another_writer(tmp_path: Path) -> None:
    # Cron chạy giữa chừng: job khác đang giữ khoá ghi → migration giành khoá TRƯỚC khi đọc bảng
    # (BEGIN IMMEDIATE); với timeout 0 nó báo bận thay vì dời trên dữ liệu đang đổi
    db_path = tmp_path / "t.db"
    _db_with_old_daily_view_labels(db_path).close()
    holder = sqlite3.connect(db_path)
    holder.execute("BEGIN IMMEDIATE")
    impatient = sqlite3.connect(db_path, timeout=0)
    impatient.row_factory = sqlite3.Row
    statements: list[str] = []
    impatient.set_trace_callback(statements.append)
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            schema_module._relabel_daily_views_to_meta_day(impatient)
    finally:
        holder.rollback()
        holder.close()
    impatient.set_trace_callback(None)
    # BEGIN hoãn (deferred) cũng báo "locked" — nhưng ở lệnh DELETE, sau khi đã đọc bảng; 2 job
    # cùng đọc "chưa có dấu" rồi cùng xin nâng khoá thì 1 job lỗi ngay (SQLite không chờ khi
    # kẹt chéo khoá)
    began = [sql for sql in statements if sql.startswith("BEGIN")]
    assert began == ["BEGIN IMMEDIATE"]
    assert not any("account_daily_views" in sql for sql in statements)
    marker = schema_module.DAILY_VIEWS_RELABEL_MIGRATION
    assert not schema_module.migration_applied(impatient, marker)
    impatient.close()
