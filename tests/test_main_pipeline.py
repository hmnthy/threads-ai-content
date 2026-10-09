"""API đọc cho landing: `/content-units` (ADR-0011), `/topics` mở rộng, `/pipeline/summary`,
`/topics/comparisons` và sàn views của bảng top (ADR-0023)."""

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
from src.pipeline.compare_topics import run_compare
from tests.pipeline.test_compare_topics import seed_clustered_channel


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


# --- /topics/comparisons (ADR-0023) ---------------------------------------------------------


def test_topic_comparisons_before_the_compare_step_ran(db_path: Path) -> None:
    data = TestClient(main_module.app).get("/topics/comparisons").json()

    assert data["cluster_run_id"] is None
    assert data["stale"] is False
    assert data["method"] is None
    assert data["rows"] == []


def test_topic_comparisons_read_the_stored_run(db_path: Path) -> None:
    seed_clustered_channel(db_path)
    run_compare(db_path, n_permutations=300)

    data = TestClient(main_module.app).get("/topics/comparisons").json()

    assert data["stale"] is False
    assert data["method"]["holm_family_size"] == 6  # UI đọc số này, không tự nhân
    assert data["method"]["min_posts_to_compare"] == MIN_N_PER_BUCKET
    assert data["snapshot_as_of"].startswith("2026-10-09T12:00:00")
    keys = [(row["metric"], row["group_id"]) for row in data["rows"]]
    assert keys[:4] == [
        ("engagement", "topic_1"),
        ("engagement", "topic_2"),
        ("engagement", "noise"),
        ("engagement", "channel"),
    ]
    topic_1 = data["rows"][0]
    assert topic_1["kind"] == "topic" and topic_1["tested"] is True
    assert topic_1["group"]["n"] == 6 and topic_1["rest"]["n"] == 10
    assert topic_1["effect_size"] == pytest.approx(1.0)
    assert topic_1["p_value_holm"] is not None
    noise = data["rows"][2]
    assert noise["rest"] is None and noise["p_value"] is None
    assert noise["group"]["excluded_no_views"] == 1


def test_stale_comparisons_hide_tests_but_keep_descriptives(db_path: Path) -> None:
    seed_clustered_channel(db_path)
    run_compare(db_path, n_permutations=300)
    conn = connect(db_path)
    # lần gom cụm mới hơn mà bước so sánh chưa chạy (VD bước compare của job lỗi)
    insert_cluster_run(
        conn,
        run_at="2026-10-10T10:30:00+00:00",
        model_id="BAAI/bge-m3",
        params={},
        n_units=17,
        n_clusters=2,
        noise_ratio=0.35,
        dbcv=None,
        ari_vs_previous=None,
        labels={},
    )
    conn.commit()
    conn.close()

    data = TestClient(main_module.app).get("/topics/comparisons").json()

    assert data["stale"] is True
    topic_rows = [row for row in data["rows"] if row["kind"] == "topic"]
    assert topic_rows
    for row in topic_rows:
        assert row["effect_size"] is None
        assert row["effect_size_ci_low"] is None and row["effect_size_ci_high"] is None
        assert row["p_value"] is None and row["p_value_holm"] is None
        assert row["group"]["n"] > 0  # mô tả vẫn trả (Thy chốt D3)


# --- sàn views cho bảng top (ADR-0023 1f) -----------------------------------------------------


def test_overview_top_tables_rank_only_posts_at_or_above_the_p25_views_floor(
    db_path: Path,
) -> None:
    conn = connect(db_path)
    # views 100/200/300/400 → P25 inclusive = 175. "few" có tỉ lệ cao nhất nhưng dưới sàn
    _root(conn, "few", "few views", views=100, likes=50)
    _root(conn, "b", "b", views=200, likes=4)
    _root(conn, "c", "c", views=300, likes=3)
    _root(conn, "d", "d", views=400, likes=2)
    conn.commit()
    conn.close()

    data = TestClient(main_module.app).get("/analytics/overview").json()

    assert data["views_floor"] == pytest.approx(175.0)
    assert data["below_views_floor"] == 1
    assert "25th percentile" in data["views_floor_rule"]
    for table in ("top_by_engagement", "top_by_share_rate", "top_by_conversation"):
        assert "few" not in [entry["id"] for entry in data[table]]
    # phân phối toàn kênh vẫn dùng mọi bài đo được — sàn chỉ áp cho bảng top
    assert data["engagement"]["n"] == 4


def test_overview_keeps_a_post_exactly_on_the_floor(db_path: Path) -> None:
    conn = connect(db_path)
    for post_id, views in (("a", 100), ("b", 100), ("c", 300)):  # P25 = 100
        _root(conn, post_id, post_id, views=views, likes=1)
    conn.commit()
    conn.close()

    data = TestClient(main_module.app).get("/analytics/overview").json()

    assert data["views_floor"] == pytest.approx(100.0)
    assert data["below_views_floor"] == 0
    assert len(data["top_by_engagement"]) == 3


# --- /topics: lịch sử tên (ADR-0023 1e) -------------------------------------------------------


def test_topics_report_label_date_and_runs_keeping_the_label(db_path: Path) -> None:
    conn = connect(db_path)
    _root(conn, "p1", "post", views=100, likes=1)
    upsert_topic(
        conn,
        topic_id="topic_1",
        label_en="Studying in France",
        description_en=None,
        method="cluster",
        labeled_at="2026-10-05T10:30:48+00:00",
        label_model="claude-sonnet-5-5",
        label_prompt_version=2,
    )
    upsert_post_topic_label(
        conn, post_id="p1", topic_id="topic_1", method="cluster", confidence=0.8
    )
    for events in (None, {"topic_1": "new"}, {"topic_1": "kept"}, {"topic_1": "kept_semantic"}):
        insert_cluster_run(
            conn,
            run_at="2026-10-05T10:30:00+00:00",
            model_id="BAAI/bge-m3",
            params={},
            n_units=1,
            n_clusters=1,
            noise_ratio=0.0,
            dbcv=None,
            ari_vs_previous=None,
            labels={"p1": 0},
            topic_events=events,
        )
    conn.commit()
    conn.close()

    (topic,) = TestClient(main_module.app).get("/topics").json()

    assert topic["labeled_at"] == "2026-10-05T10:30:48+00:00"
    assert (topic["label_model"], topic["label_prompt_version"]) == ("claude-sonnet-5-5", 2)
    assert topic["runs_keeping_label"] == 2  # 2 lần giữ tên liền sau lần đặt tên (`new`)
