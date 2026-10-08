"""API đọc cho landing: `/content-units` (ADR-0011), `/topics` mở rộng và `/pipeline/summary`."""

import sqlite3
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.main as main_module
from src.analysis.stats import MIN_N_PER_BUCKET
from src.api.models import MediaType, ThreadsPost
from src.db.schema import (
    connect,
    create_schema,
    insert_cluster_run,
    insert_insight_snapshot,
    update_reply_roles,
    upsert_content_unit,
    upsert_embedding,
    upsert_post,
    upsert_post_topic_label,
    upsert_topic,
)
from src.models.content_unit import ContentUnit
from src.models.insight_snapshot import InsightSnapshot


def _root(
    conn: sqlite3.Connection, post_id: str, text: str, *, views: int | None, likes: int = 0
) -> None:
    post = ThreadsPost(
        id=post_id,
        text=text,
        timestamp=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
    )
    upsert_post(conn, post)
    upsert_content_unit(conn, ContentUnit(root=post, full_text=text))
    if views is not None:
        insert_insight_snapshot(
            conn,
            InsightSnapshot(
                post_id=post_id,
                fetched_at=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
                views=views,
                likes=likes,
                replies=0,
                reposts=0,
                quotes=0,
            ),
        )


def _reply(conn: sqlite3.Connection, post_id: str) -> None:
    upsert_post(
        conn,
        ThreadsPost(
            id=post_id,
            text="reply",
            timestamp=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
            media_type=MediaType.TEXT_POST,
            is_reply=True,
            root_post={"id": "a"},
            replied_to={"id": "a"},
        ),
    )


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path]:
    path = tmp_path / "landing.db"
    monkeypatch.setattr(main_module, "DEFAULT_DB_PATH", path)
    conn = connect(path)
    create_schema(conn)
    conn.commit()
    conn.close()
    yield path


def test_content_units_metrics_are_null_when_latest_snapshot_has_no_views(db_path: Path) -> None:
    conn = connect(db_path)
    _root(conn, "measured", "measured", views=200, likes=10)
    _root(conn, "zero", "zero views", views=0)
    conn.commit()
    conn.close()

    data = {unit["id"]: unit for unit in TestClient(main_module.app).get("/content-units").json()}

    assert data["measured"]["metrics"]["engagement_rate"] == pytest.approx(5.0)
    # ADR-0011: views = 0 là insight thiếu — không trả rate 0.0 giả
    assert data["zero"]["metrics"] is None


def test_topics_report_profile_and_engagement_of_measurable_members(db_path: Path) -> None:
    conn = connect(db_path)
    # 5 bài đo được (engagement 1, 2, 3, 4, 5 %) + 1 bài views = 0
    for i in range(1, 6):
        _root(conn, f"p{i}", f"post {i}", views=100, likes=i)
    _root(conn, "p0", "no views yet", views=0)
    upsert_topic(
        conn,
        topic_id="topic_1",
        label_en="Studying in France",
        description_en=None,
        method="cluster",
        keywords=["học", "tiếng pháp"],
        # "gone" không còn content unit → bị bỏ, giữ thứ tự còn lại
        representative_ids=["p3", "gone", "p1"],
    )
    for i, post_id in enumerate(["p0", "p1", "p2", "p3", "p4", "p5"]):
        upsert_post_topic_label(
            conn, post_id=post_id, topic_id="topic_1", method="cluster", confidence=0.5 + i / 100
        )
    conn.commit()
    conn.close()

    (topic,) = TestClient(main_module.app).get("/topics").json()

    assert topic["post_count"] == 6
    assert topic["keywords"] == ["học", "tiếng pháp"]
    assert [rep["id"] for rep in topic["representatives"]] == ["p3", "p1"]
    assert topic["representatives"][0]["full_text"] == "post 3"
    assert topic["representatives"][0]["centroid_similarity"] == pytest.approx(0.53)
    assert topic["excluded_no_views"] == 1
    assert topic["engagement"]["n"] == 5
    assert topic["engagement"]["median"] == pytest.approx(3.0)
    assert topic["engagement"]["iqr_low"] == pytest.approx(2.0)
    assert topic["engagement"]["iqr_high"] == pytest.approx(4.0)
    assert topic["engagement"]["insufficient_data"] is False


def test_topic_without_profile_has_empty_keywords_and_small_n_flag(db_path: Path) -> None:
    conn = connect(db_path)
    for i in range(1, 5):
        _root(conn, f"p{i}", f"post {i}", views=100, likes=i)
    upsert_topic(conn, topic_id="topic_2", label_en="Food", description_en=None, method="cluster")
    for i in range(1, 5):
        upsert_post_topic_label(
            conn, post_id=f"p{i}", topic_id="topic_2", method="cluster", confidence=None
        )
    conn.commit()
    conn.close()

    (topic,) = TestClient(main_module.app).get("/topics").json()

    assert topic["keywords"] == []
    assert topic["representatives"] == []
    # 4 bài < MIN_N_PER_BUCKET = 5 → cờ n nhỏ duy nhất của dự án (UI-L20260903-small-n-flag)
    assert topic["engagement"]["n"] == 4
    assert topic["engagement"]["insufficient_data"] is True


def test_pipeline_summary_counts_units_roles_and_reads_latest_run(db_path: Path) -> None:
    conn = connect(db_path)
    _root(conn, "a", "first post", views=100, likes=3)
    _root(conn, "b", "second post", views=100, likes=1)
    _root(conn, "c", "noise with no views", views=0)
    _root(conn, "img", "   ", views=None)  # bài chỉ có ảnh: không có chữ để embed
    for reply_id in ["r1", "r2", "r3", "r4", "r5"]:
        _reply(conn, reply_id)
    update_reply_roles(
        conn,
        {"r1": "self_continuation", "r2": "author_answer", "r3": "author_answer", "r4": "outbound"},
    )
    upsert_embedding(
        conn,
        object_type="content_unit",
        object_id="a",
        model_id="BAAI/bge-m3",
        text_hash="h",
        vector=[0.0] * 4,
        created_at="2026-10-01T11:00:00+00:00",
    )
    for run_at, labels, noise_ratio, dbcv, ari, ari_clustered in [
        ("2026-09-30T10:00:00+00:00", {"a": 0, "b": 0, "c": 0}, 0.0, None, None, None),
        ("2026-10-01T11:35:06+00:00", {"a": 0, "b": -1, "c": -1}, 2 / 3, 0.3, 0.2, 0.8),
    ]:
        insert_cluster_run(
            conn,
            run_at=run_at,
            model_id="BAAI/bge-m3",
            params={"umap_n_neighbors": 8},
            n_units=3,
            n_clusters=1,
            noise_ratio=noise_ratio,
            dbcv=dbcv,
            ari_vs_previous=ari,
            ari_clustered_only=ari_clustered,
            labels=labels,
        )
    conn.commit()
    conn.close()

    data = TestClient(main_module.app).get("/pipeline/summary").json()

    assert data["content_units"] == 4
    assert data["units_without_text"] == 1
    assert data["reply_roles"] == {
        "self_continuation": 1,
        "author_answer": 2,
        "outbound": 1,
        "unassigned": 1,
    }
    assert data["latest_snapshot_at"].startswith("2026-10-01T12:00:00")
    run = data["latest_cluster_run"]
    assert run["run_at"] == "2026-10-01T11:35:06+00:00"
    assert run["params"] == {"umap_n_neighbors": 8}
    assert run["embedding_dim"] == 4
    assert (run["n_units"], run["n_clusters"], run["n_noise"]) == (3, 1, 2)
    assert run["dbcv"] == pytest.approx(0.3)
    assert run["ari_vs_previous"] == pytest.approx(0.2)
    assert run["ari_clustered_only"] == pytest.approx(0.8)
    # bài nhiễu: "b" đo được, "c" views = 0 → loại và báo số
    assert data["noise_engagement"]["n"] == 1
    assert data["noise_engagement"]["median"] == pytest.approx(1.0)
    assert data["noise_excluded_no_views"] == 1
    # UI ghi đúng ngưỡng của backend, không tự đặt ngưỡng thứ hai
    assert data["min_posts_to_compare"] == MIN_N_PER_BUCKET


def test_pipeline_summary_before_any_cluster_run(db_path: Path) -> None:
    data = TestClient(main_module.app).get("/pipeline/summary").json()

    assert data["content_units"] == 0
    assert data["latest_snapshot_at"] is None
    assert data["latest_cluster_run"] is None
    assert data["noise_engagement"] is None
    assert data["noise_excluded_no_views"] == 0
