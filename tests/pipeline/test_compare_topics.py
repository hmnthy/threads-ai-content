"""Bước `compare` của job NLP (ADR-0023): đọc lần gom cụm mới nhất, ghi `topic_comparisons`."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.api.models import MediaType, ThreadsPost
from src.db.schema import (
    connect,
    create_schema,
    insert_cluster_run,
    insert_insight_snapshot,
    latest_topic_comparison_run,
    list_topic_comparisons,
    replace_topic_comparisons,
    upsert_content_unit,
    upsert_post,
    upsert_post_topic_label,
    upsert_topic,
)
from src.models.content_unit import ContentUnit
from src.models.insight_snapshot import InsightSnapshot
from src.pipeline.compare_topics import run_compare

N_PERM = 300


def _unit(conn: sqlite3.Connection, unit_id: str, *, views: int, likes: int, day: int) -> None:
    post = ThreadsPost(
        id=unit_id,
        text=unit_id,
        timestamp=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
    )
    upsert_post(conn, post)
    upsert_content_unit(conn, ContentUnit(root=post, full_text=unit_id))
    insert_insight_snapshot(
        conn,
        InsightSnapshot(
            post_id=unit_id,
            fetched_at=datetime(2026, 10, day, 12, 0, tzinfo=UTC),
            views=views,
            likes=likes,
            replies=0,
            reposts=0,
            quotes=0,
        ),
    )


def seed_clustered_channel(db_path: Path) -> None:
    """topic_1: 6 bài, topic_2: 5 bài, nhiễu: 6 bài (1 bài views = 0); 1 lần gom cụm."""
    conn = connect(db_path)
    create_schema(conn)
    labels: dict[str, int] = {}
    for i in range(6):
        _unit(conn, f"t1_{i}", views=1000, likes=60 + i, day=8)
        labels[f"t1_{i}"] = 0
    for i in range(5):
        _unit(conn, f"t2_{i}", views=1000, likes=20 + i, day=8)
        labels[f"t2_{i}"] = 1
    for i in range(5):
        _unit(conn, f"n_{i}", views=1000, likes=10 + 4 * i, day=7)
        labels[f"n_{i}"] = -1
    _unit(conn, "n_zero", views=0, likes=0, day=9)  # snapshot mới nhất của kênh
    labels["n_zero"] = -1
    for topic_id, label in (("topic_1", 0), ("topic_2", 1)):
        upsert_topic(
            conn, topic_id=topic_id, label_en=topic_id, description_en=None, method="cluster"
        )
        for unit_id, unit_label in labels.items():
            if unit_label == label:
                upsert_post_topic_label(
                    conn, post_id=unit_id, topic_id=topic_id, method="cluster", confidence=0.8
                )
    insert_cluster_run(
        conn,
        run_at="2026-10-09T10:30:00+00:00",
        model_id="BAAI/bge-m3",
        params={},
        n_units=len(labels),
        n_clusters=2,
        noise_ratio=6 / 17,
        dbcv=None,
        ari_vs_previous=None,
        labels=labels,
    )
    conn.commit()
    conn.close()


def test_run_compare_stores_every_topic_metric_with_holm_family(tmp_path: Path) -> None:
    db_path = tmp_path / "t.db"
    seed_clustered_channel(db_path)

    summary = run_compare(db_path, n_permutations=N_PERM)

    conn = connect(db_path)
    run = latest_topic_comparison_run(conn)
    assert run is not None
    rows = list_topic_comparisons(conn, run["cluster_run_id"])
    conn.close()
    assert summary["holm_family_size"] == run["holm_family_size"] == 2 * 3
    assert (run["n_permutations"], run["random_seed"]) == (N_PERM, 0)
    # snapshot mới nhất trong các snapshot đã dùng (bài views = 0 vẫn có snapshot)
    assert run["snapshot_as_of"].startswith("2026-10-09T12:00:00")
    assert len(rows) == 4 * 3  # 2 topic + nhiễu + kênh, × 3 chỉ số
    by_key = {(r["group_id"], r["metric"]): r for r in rows}
    noise = by_key[("noise", "engagement")]
    assert (noise["n"], noise["excluded_no_views"], noise["tested"]) == (5, 1, 0)
    topic_1 = by_key[("topic_1", "engagement")]
    assert (topic_1["n"], topic_1["rest_n"], topic_1["tested"]) == (6, 10, 1)
    assert topic_1["effect_size"] == pytest.approx(1.0)  # 6 bài cao nhất kênh
    assert topic_1["p_value_holm"] >= topic_1["p_value"]


def test_rerunning_the_same_cluster_run_replaces_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "t.db"
    seed_clustered_channel(db_path)

    run_compare(db_path, n_permutations=N_PERM)
    run_compare(db_path, n_permutations=N_PERM)

    conn = connect(db_path)
    n_runs = conn.execute("SELECT COUNT(*) FROM topic_comparison_runs").fetchone()[0]
    n_rows = conn.execute("SELECT COUNT(*) FROM topic_comparisons").fetchone()[0]
    conn.close()
    assert (n_runs, n_rows) == (1, 12)


def test_replace_refuses_an_open_transaction(tmp_path: Path) -> None:
    # Hàm tự commit — không được commit/rollback lén việc dở của người gọi
    conn = connect(tmp_path / "t.db")
    create_schema(conn)
    conn.execute("INSERT INTO account_daily_views VALUES ('2026-10-01', 1, 'x')")
    assert conn.in_transaction
    with pytest.raises(RuntimeError, match="transaction"):
        replace_topic_comparisons(
            conn,
            cluster_run_id=1,
            computed_at="x",
            snapshot_as_of=None,
            n_permutations=1,
            random_seed=0,
            holm_family_size=0,
            rows=[],
        )
    conn.close()


def test_latest_comparison_run_on_a_database_before_migration(tmp_path: Path) -> None:
    # API không gọi create_schema: DB cũ chưa có bảng → "chưa có kết quả", không lỗi
    conn = connect(tmp_path / "old.db")
    assert latest_topic_comparison_run(conn) is None
    conn.close()


def test_run_compare_without_any_cluster_run_is_a_no_op(tmp_path: Path) -> None:
    summary = run_compare(tmp_path / "empty.db", n_permutations=N_PERM)

    assert "skipped" in summary
