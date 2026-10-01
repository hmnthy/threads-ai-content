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


def _write_full_results(path: Path, ids: list[str], labels: list[int]) -> None:
    """Định dạng mới (ADR-0004): kèm embedding, hash, DBCV, tham số."""
    vectors = {
        0: [1.0, 0.0],
        1: [0.0, 1.0],
        -1: [0.7071, 0.7071],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "model_name": "BAAI/bge-m3",
                "ids": ids,
                "hashes": [f"h-{uid}" for uid in ids],
                "cluster_labels": labels,
                "umap_coords": [[float(i), 0.0, 0.0] for i in range(len(ids))],
                "embeddings": [vectors[label] for label in labels],
                "dbcv": 0.3,
                "params": {"hdbscan_min_cluster_size": 4},
            }
        ),
        encoding="utf-8",
    )


def test_run_import_stores_embeddings_profiles_and_run_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    results_path = tmp_path / "cluster_results.json"
    unit_ids = ["u1", "u2", "u3", "u4", "u5"]
    _seed_content_units(db_path, unit_ids)
    monkeypatch.setattr(clustering_import, "RESULTS_PATH", results_path)
    seen_samples: list[list[str]] = []

    def _recording_label(sample_texts: list[str], client: Any = None) -> TopicLabelResult:
        seen_samples.append(sample_texts)
        return TopicLabelResult(label_en="Topic", description_en="About it.")

    monkeypatch.setattr(clustering_import, "label_cluster_with_claude", _recording_label)

    # Lần 1 (định dạng cũ, không embedding) → có nhãn "trước" để tính ARI ở lần 2
    _write_results(results_path, unit_ids, [0, 0, 1, 1, -1])
    clustering_import.run_import(db_path=db_path)

    _write_full_results(results_path, unit_ids, [0, 0, 1, 1, -1])
    stats = clustering_import.run_import(db_path=db_path)

    assert stats["ari_vs_previous"] == pytest.approx(1.0)  # cùng cách chia
    assert stats["dbcv_validity_index"] == 0.3
    assert stats["ari_clustered_only"] == pytest.approx(1.0)
    assert stats["transitions"]["cluster_to_noise"] == 0
    assert stats["transitions"]["noise_to_noise"] == 1
    conn = connect(db_path)
    n_vectors = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    assert n_vectors == 5
    topic = conn.execute("SELECT * FROM topics WHERE id = 'cluster_0'").fetchone()
    assert json.loads(topic["representative_ids_json"]) == ["u1", "u2"]
    assert json.loads(topic["keywords_json"]) == ["content for"]
    run = conn.execute("SELECT * FROM cluster_runs ORDER BY id DESC").fetchone()
    assert run["n_clusters"] == 2
    assert run["noise_ratio"] == pytest.approx(0.2)
    assert json.loads(run["labels_json"]) == {"u1": 0, "u2": 0, "u3": 1, "u4": 1, "u5": -1}
    confidence = conn.execute(
        "SELECT confidence FROM post_topic_labels WHERE post_id = 'u1'"
    ).fetchone()[0]
    assert confidence == pytest.approx(1.0)
    conn.close()


def test_run_import_dry_run_writes_nothing_and_skips_claude(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    results_path = tmp_path / "cluster_results.json"
    unit_ids = ["u1", "u2", "u3", "u4", "u5"]
    _seed_content_units(db_path, unit_ids)
    monkeypatch.setattr(clustering_import, "RESULTS_PATH", results_path)

    def _must_not_call(sample_texts: list[str], client: Any = None) -> TopicLabelResult:
        raise AssertionError("dry_run không được gọi Claude")

    monkeypatch.setattr(clustering_import, "label_cluster_with_claude", _must_not_call)
    _write_full_results(results_path, unit_ids, [0, 0, 1, 1, -1])

    stats = clustering_import.run_import(db_path=db_path, dry_run=True)

    assert stats["n_clusters_labeled"] == 2
    assert stats["cluster_sizes"] == [2, 2]
    conn = connect(db_path)
    for table in ("topics", "embeddings", "cluster_runs"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    conn.close()


def test_compare_with_previous_separates_noise_moves_from_regrouping() -> None:
    previous = {"a": 0, "b": 0, "c": 1, "d": 1, "e": 1}
    current = {"a": 0, "b": 0, "c": 1, "d": 1, "e": -1, "f": 2}
    ari_all, ari_clustered, transitions = clustering_import.compare_with_previous(previous, current)
    assert ari_clustered == pytest.approx(1.0)  # bài có cụm ở cả 2 lần: chia y hệt
    assert ari_all is not None and ari_all < 1.0  # chỉ vì 1 bài chuyển sang nhiễu
    assert transitions == {
        "cluster_to_cluster": 4,
        "cluster_to_noise": 1,
        "noise_to_cluster": 0,
        "noise_to_noise": 0,
        "new_units": 1,
    }


def test_claude_failure_leaves_previous_topics_and_runs_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    results_path = tmp_path / "cluster_results.json"
    unit_ids = ["u1", "u2", "u3", "u4", "u5"]
    _seed_content_units(db_path, unit_ids)
    monkeypatch.setattr(clustering_import, "RESULTS_PATH", results_path)
    monkeypatch.setattr(clustering_import, "label_cluster_with_claude", _fake_label)
    _write_full_results(results_path, unit_ids, [0, 0, 0, 0, -1])
    clustering_import.run_import(db_path=db_path)

    calls = {"n": 0}

    def _fails_on_second(sample_texts: list[str], client: Any = None) -> TopicLabelResult:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("API down")
        return TopicLabelResult(label_en="New", description_en="New.")

    monkeypatch.setattr(clustering_import, "label_cluster_with_claude", _fails_on_second)
    _write_full_results(results_path, unit_ids, [0, 0, 1, 1, -1])
    with pytest.raises(RuntimeError):
        clustering_import.run_import(db_path=db_path)

    conn = connect(db_path)
    assert {r["label_en"] for r in conn.execute("SELECT label_en FROM topics")} == {"Fake topic"}
    assert conn.execute("SELECT COUNT(*) FROM cluster_runs").fetchone()[0] == 1
    conn.close()


def test_baseline_db_is_used_as_previous_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit_ids = ["u1", "u2", "u3", "u4", "u5"]
    baseline = tmp_path / "baseline.db"
    current = tmp_path / "current.db"
    results_path = tmp_path / "cluster_results.json"
    monkeypatch.setattr(clustering_import, "RESULTS_PATH", results_path)
    monkeypatch.setattr(clustering_import, "label_cluster_with_claude", _fake_label)
    for db in (baseline, current):
        _seed_content_units(db, unit_ids)
    # Baseline: chia {u1,u2,u3} / {u4} — khác hẳn cách chia mới
    _write_full_results(results_path, unit_ids, [0, 0, 0, 1, -1])
    clustering_import.run_import(db_path=baseline)

    _write_full_results(results_path, unit_ids, [0, 0, 1, 1, -1])
    same_db = clustering_import.run_import(db_path=current, dry_run=True)
    vs_baseline = clustering_import.run_import(db_path=current, dry_run=True, baseline_db=baseline)
    assert same_db["ari_vs_previous"] is None  # DB mới chưa có lần chạy nào để so
    assert vs_baseline["ari_vs_previous"] is not None
    assert vs_baseline["ari_vs_previous"] < 1.0


def test_import_refuses_stale_results_from_a_failed_wsl_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    results_path = tmp_path / "cluster_results.json"
    export_path = tmp_path / "texts_export.json"
    _seed_content_units(db_path, ["u1", "u2"])
    monkeypatch.setattr(clustering_import, "RESULTS_PATH", results_path)
    monkeypatch.setattr(clustering_import, "EXPORT_PATH", export_path)
    export_path.write_text('{"ids": ["u1", "u2"], "texts": ["a", "b"]}', encoding="utf-8")
    results_path.write_text(
        json.dumps(
            {
                "export_digest": "digest-of-yesterdays-export",
                "ids": ["u1", "u2"],
                "cluster_labels": [0, 0],
                "umap_coords": [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="không khớp"):
        clustering_import.run_import(db_path=db_path)


def test_import_clears_coordinates_of_units_no_longer_clustered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    results_path = tmp_path / "cluster_results.json"
    _seed_content_units(db_path, ["u1", "u2", "u3"])
    monkeypatch.setattr(clustering_import, "RESULTS_PATH", results_path)
    monkeypatch.setattr(clustering_import, "label_cluster_with_claude", _fake_label)
    _write_results(results_path, ["u1", "u2", "u3"], [0, 0, -1])
    clustering_import.run_import(db_path=db_path)
    # Lần sau u3 không còn chữ → không có trong export/kết quả
    _write_results(results_path, ["u1", "u2"], [0, 0])
    clustering_import.run_import(db_path=db_path)
    conn = connect(db_path)
    assert conn.execute("SELECT umap_x FROM content_units WHERE id = 'u3'").fetchone()[0] is None
    conn.close()
