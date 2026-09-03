"""Layer 10 — verify `run_import()` không tích rác `topics`/`post_topic_labels`
(`method='cluster'`) khi chạy 2 lần liên tiếp với số cluster/thành phần khác nhau.

Bug gốc: `topic_id = f"cluster_{n}"` lấy theo VỊ TRÍ nhãn HDBSCAN — không ổn định
giữa các lần chạy — và code cũ chỉ dùng `upsert` (không xoá trước), nên cluster
biến mất ở lần chạy sau vẫn tồn tại vĩnh viễn trong DB. Test giả lập đúng kịch
bản đó: lần 1 có `cluster_0` VÀ `cluster_1`, lần 2 chỉ còn `cluster_0` — sau lần
2, `cluster_1` phải biến mất hoàn toàn khỏi cả 2 bảng.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from src.api.models import MediaType, ThreadsPost
from src.db.schema import connect, create_schema, upsert_content_unit, upsert_post
from src.models.content_unit import ContentUnit
from src.nlp.topics import TopicLabelResult
from src.pipeline import clustering_import


def _seed_content_units(db_path: Path, unit_ids: list[str]) -> None:
    conn = connect(db_path)
    create_schema(conn)
    for uid in unit_ids:
        post = ThreadsPost(
            id=uid,
            timestamp=datetime(2026, 8, 24, 9, 0, tzinfo=UTC),
            media_type=MediaType.TEXT_POST,
        )
        upsert_post(conn, post)
        upsert_content_unit(conn, ContentUnit(root=post, full_text=f"content for {uid}"))
    conn.commit()
    conn.close()


def _write_results(path: Path, ids: list[str], cluster_labels: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    umap_coords = [[float(i), float(i), float(i)] for i in range(len(ids))]
    path.write_text(
        json.dumps({"ids": ids, "cluster_labels": cluster_labels, "umap_coords": umap_coords}),
        encoding="utf-8",
    )


def _fake_label(sample_texts: list[str], client: Any = None) -> TopicLabelResult:
    return TopicLabelResult(label_en="Fake topic", description_en="Fake description.")


def test_run_import_twice_does_not_leave_stale_cluster_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    results_path = tmp_path / "cluster_results.json"
    unit_ids = ["u1", "u2", "u3", "u4", "u5"]
    _seed_content_units(db_path, unit_ids)

    monkeypatch.setattr(clustering_import, "RESULTS_PATH", results_path)
    monkeypatch.setattr(clustering_import, "label_cluster_with_claude", _fake_label)

    # Lần 1: cluster_0 = {u1, u2}, cluster_1 = {u3, u4}, u5 = noise (-1).
    _write_results(results_path, unit_ids, [0, 0, 1, 1, -1])
    stats_1 = clustering_import.run_import(db_path=db_path)
    assert stats_1["n_clusters_labeled"] == 2

    conn = connect(db_path)
    topics_after_1 = {row["id"] for row in conn.execute("SELECT id FROM topics").fetchall()}
    assert topics_after_1 == {"cluster_0", "cluster_1"}
    conn.close()

    # Lần 2: chỉ còn cluster_0 = {u1, u2, u3, u4} — cluster_1 biến mất hoàn toàn
    # (giả lập HDBSCAN gom lại khác đi giữa 2 lần chạy, đúng bug đã xác nhận).
    _write_results(results_path, unit_ids, [0, 0, 0, 0, -1])
    stats_2 = clustering_import.run_import(db_path=db_path)
    assert stats_2["n_clusters_labeled"] == 1

    conn = connect(db_path)
    topics_after_2 = conn.execute("SELECT id, method FROM topics").fetchall()
    assert [dict(row) for row in topics_after_2] == [{"id": "cluster_0", "method": "cluster"}]

    labels_after_2 = conn.execute(
        "SELECT post_id, topic_id FROM post_topic_labels WHERE method = 'cluster'"
    ).fetchall()
    assert {row["topic_id"] for row in labels_after_2} == {"cluster_0"}
    assert {row["post_id"] for row in labels_after_2} == {"u1", "u2", "u3", "u4"}
    conn.close()


def test_run_import_preserves_fixed_method_topics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`delete_cluster_topics()` chỉ xoá method='cluster' — method='fixed' (chưa
    có code nào ghi, nhưng schema đã hỗ trợ) phải sống sót qua run_import()."""
    db_path = tmp_path / "test.db"
    results_path = tmp_path / "cluster_results.json"
    unit_ids = ["u1", "u2"]
    _seed_content_units(db_path, unit_ids)

    conn = connect(db_path)
    conn.execute("INSERT INTO topics (id, label_en, method) VALUES ('fixed-cv', 'CV', 'fixed')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(clustering_import, "RESULTS_PATH", results_path)
    monkeypatch.setattr(clustering_import, "label_cluster_with_claude", _fake_label)

    _write_results(results_path, unit_ids, [0, -1])
    clustering_import.run_import(db_path=db_path)

    conn = connect(db_path)
    fixed_row = conn.execute("SELECT id FROM topics WHERE method = 'fixed'").fetchone()
    assert fixed_row is not None
    assert fixed_row["id"] == "fixed-cv"
    conn.close()
