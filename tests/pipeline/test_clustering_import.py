"""Layer 10 — verify `run_import()` không tích rác `topics`/`post_topic_labels`
(`method='cluster'`) khi chạy 2 lần liên tiếp với số cluster/thành phần khác nhau.

Bug gốc: `topic_id = f"cluster_{n}"` lấy theo VỊ TRÍ nhãn HDBSCAN — không ổn định
giữa các lần chạy — và code cũ chỉ dùng `upsert` (không xoá trước), nên cluster
biến mất ở lần chạy sau vẫn tồn tại vĩnh viễn trong DB. Test giả lập đúng kịch
bản đó: lần 1 có 2 cụm, lần 2 chỉ còn 1 cụm gồm cả 2 — sau lần 2, 2 topic cũ phải biến
mất hoàn toàn khỏi cả 2 bảng. Từ ADR-0018 id là `topic_N` bền; lần 2 là ca NHẬP cụm →
id mới.
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
from src.nlp.topic_identity import TopicMatch
from src.nlp.topics import CLUSTER_LABELING_MODEL, LABEL_PROMPT_VERSION, TopicLabelResult
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
    assert topics_after_1 == {"topic_0", "topic_1"}
    conn.close()

    # Lần 2: chỉ còn 1 cụm = {u1, u2, u3, u4} — nhập 2 topic cũ (ADR-0018: id + tên mới)
    # (giả lập HDBSCAN gom lại khác đi giữa 2 lần chạy, đúng bug đã xác nhận).
    _write_results(results_path, unit_ids, [0, 0, 0, 0, -1])
    stats_2 = clustering_import.run_import(db_path=db_path)
    assert stats_2["n_clusters_labeled"] == 1

    conn = connect(db_path)
    topics_after_2 = conn.execute("SELECT id, method FROM topics").fetchall()
    assert [dict(row) for row in topics_after_2] == [{"id": "topic_2", "method": "cluster"}]

    labels_after_2 = conn.execute(
        "SELECT post_id, topic_id FROM post_topic_labels WHERE method = 'cluster'"
    ).fetchall()
    assert {row["topic_id"] for row in labels_after_2} == {"topic_2"}
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
    # ADR-0018: cùng thành viên → giữ id + tên, không gọi Claude lần 2
    assert stats["topic_events"] == {"topic_0": "kept", "topic_1": "kept"}
    assert stats["n_named_now"] == 0
    assert len(seen_samples) == 2  # chỉ 2 lần gọi của lần chạy đầu
    assert stats["dbcv_validity_index"] == 0.3
    assert stats["ari_clustered_only"] == pytest.approx(1.0)
    assert stats["transitions"]["cluster_to_noise"] == 0
    assert stats["transitions"]["noise_to_noise"] == 1
    conn = connect(db_path)
    n_vectors = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    assert n_vectors == 5
    topic = conn.execute("SELECT * FROM topics WHERE id = 'topic_0'").fetchone()
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


# --- ADR-0018: danh tính cụm bền ---------------------------------------------------


def _state(
    labeled_at: str | None = "2026-10-04T10:00:00+00:00",
    model: str | None = None,
    version: int | None = None,
) -> Any:
    return {
        "label_en": "Old",
        "description_en": "Old.",
        "labeled_at": labeled_at,
        "label_model": model or CLUSTER_LABELING_MODEL,
        "label_prompt_version": version or LABEL_PROMPT_VERSION,
        "label_anchor_json": "[]",
    }


def test_plan_keeps_names_unless_drifted_or_labeled_with_another_config() -> None:
    kept = {i: TopicMatch(i, "kept", f"topic_{i}", (f"topic_{i}",), "membership") for i in range(5)}
    states = {
        "topic_0": _state(),
        "topic_1": _state(),  # đã trôi khỏi bản neo
        "topic_2": _state(model="an-older-model"),
        "topic_3": _state(version=1),
        "topic_4": _state(labeled_at=None),  # DB trước ADR-0018: chưa có mốc
    }
    plans = clustering_import.plan_topic_names(kept, states, 9, drifted={1})
    assert [plans[i].reason for i in range(5)] == [
        None,
        "drift",
        "config_change",
        "config_change",
        "config_change",
    ]
    assert [plans[i].topic_id for i in range(5)] == [f"topic_{i}" for i in range(5)]


def test_plan_gives_new_split_and_merged_clusters_fresh_sequential_ids() -> None:
    matches = {
        0: TopicMatch(0, "split", None, ("topic_1",)),
        1: TopicMatch(1, "split", None, ("topic_1",)),
        2: TopicMatch(2, "merged", None, ("topic_2", "topic_3")),
        3: TopicMatch(3, "new", None, ()),
    }
    plans = clustering_import.plan_topic_names(matches, {}, 7, drifted=set())
    assert [(p.topic_id, p.reason) for p in plans.values()] == [
        ("topic_7", "split"),
        ("topic_8", "split"),
        ("topic_9", "merged"),
        ("topic_10", "new"),
    ]


def _counting_labeler(calls: list[int]) -> Any:
    def _label(sample_texts: list[str], client: Any = None) -> TopicLabelResult:
        calls.append(len(sample_texts))
        return TopicLabelResult(label_en=f"Topic {len(calls)}", description_en="About it.")

    return _label


def test_core_keeps_name_fragment_is_new_and_history_records_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    results_path = tmp_path / "cluster_results.json"
    unit_ids = [f"u{i}" for i in range(10)]
    _seed_content_units(db_path, unit_ids)
    monkeypatch.setattr(clustering_import, "RESULTS_PATH", results_path)
    calls: list[int] = []
    monkeypatch.setattr(clustering_import, "label_cluster_with_claude", _counting_labeler(calls))

    _write_results(results_path, unit_ids, [0] * 10)  # 1 cụm 10 bài
    assert clustering_import.run_import(db_path=db_path)["topic_events"] == {"topic_0": "new"}

    _write_results(results_path, unit_ids, [0] * 6 + [1] * 4)  # lõi 6 + mảnh 4
    second = clustering_import.run_import(db_path=db_path)
    assert second["topic_events"] == {"topic_0": "kept", "topic_1": "new"}
    assert len(calls) == 2  # lõi giữ tên: chỉ mảnh mới được đặt tên

    conn = connect(db_path)
    history = conn.execute(
        "SELECT topic_id, reason, sources_json FROM topic_label_history ORDER BY id"
    ).fetchall()
    assert [(h["topic_id"], h["reason"], json.loads(h["sources_json"])) for h in history] == [
        ("topic_0", "new", []),
        ("topic_1", "new", ["topic_0"]),
    ]
    run = conn.execute("SELECT topic_events_json FROM cluster_runs ORDER BY id DESC").fetchone()
    assert json.loads(run["topic_events_json"]) == second["topic_events"]
    anchor = conn.execute("SELECT label_anchor_json FROM topics WHERE id = 'topic_1'").fetchone()
    assert json.loads(anchor[0]) == ["u6", "u7", "u8", "u9"]
    conn.close()


def test_cumulative_drift_relabels_even_when_each_run_keeps_the_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    results_path = tmp_path / "cluster_results.json"
    unit_ids = [f"u{i}" for i in range(12)]
    _seed_content_units(db_path, unit_ids)
    monkeypatch.setattr(clustering_import, "RESULTS_PATH", results_path)
    calls: list[int] = []
    monkeypatch.setattr(clustering_import, "label_cluster_with_claude", _counting_labeler(calls))

    def run(members: set[int]) -> dict[str, str]:
        labels = [0 if i in members else -1 for i in range(12)]
        _write_results(results_path, unit_ids, labels)
        events: dict[str, str] = clustering_import.run_import(db_path=db_path)["topic_events"]
        return events

    assert run({0, 1, 2, 3, 4, 5}) == {"topic_0": "new"}  # bản neo = u0..u5
    # Mỗi lần thay 2 bài: so với lần trước vẫn là đa số → giữ id; so với bản neo thì trôi dần
    assert run({2, 3, 4, 5, 6, 7}) == {"topic_0": "kept"}
    assert run({4, 5, 6, 7, 8, 9}) == {"topic_0": "relabeled"}  # còn 2/6 bài của bản neo
    assert len(calls) == 2
    conn = connect(db_path)
    reasons = [r[0] for r in conn.execute("SELECT reason FROM topic_label_history ORDER BY id")]
    assert reasons == ["new", "drift"]
    conn.close()


def test_vanished_topic_id_is_never_reused_even_right_after_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    results_path = tmp_path / "cluster_results.json"
    unit_ids = [f"u{i}" for i in range(8)]
    _seed_content_units(db_path, unit_ids)
    conn = connect(db_path)
    # Trạng thái thật trước ADR-0018: id theo vị trí, chưa có lịch sử tên
    for n in (0, 1):
        conn.execute(
            "INSERT INTO topics (id, label_en, method) VALUES (?, 'Old', 'cluster')",
            (f"cluster_{n}",),
        )
    for i, uid in enumerate(unit_ids):
        conn.execute(
            "INSERT INTO post_topic_labels (post_id, topic_id, method) VALUES (?, ?, 'cluster')",
            (uid, f"cluster_{i // 4}"),
        )
    conn.commit()
    conn.close()
    monkeypatch.setattr(clustering_import, "RESULTS_PATH", results_path)
    monkeypatch.setattr(clustering_import, "label_cluster_with_claude", _fake_label)

    # Lần 1 sau migration: topic_1 tan vào nhiễu, không có cụm mới nào
    _write_results(results_path, unit_ids, [0] * 4 + [-1] * 4)
    first = clustering_import.run_import(db_path=db_path)
    assert first["topic_events"] == {"topic_0": "relabeled", "topic_1": "retired"}
    # Lần 2: 1 cụm mới hoàn toàn → phải là topic_2, không phải topic_1
    _write_results(results_path, unit_ids, [-1] * 4 + [0] * 4)
    second = clustering_import.run_import(db_path=db_path)
    assert "topic_1" not in second["topic_events"]
    assert second["topic_events"]["topic_2"] == "new"


def test_dry_run_reports_planned_topic_events_without_claude(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    results_path = tmp_path / "cluster_results.json"
    unit_ids = ["u1", "u2", "u3", "u4"]
    _seed_content_units(db_path, unit_ids)
    monkeypatch.setattr(clustering_import, "RESULTS_PATH", results_path)
    monkeypatch.setattr(clustering_import, "label_cluster_with_claude", _fake_label)
    _write_results(results_path, unit_ids, [0, 0, 1, 1])
    clustering_import.run_import(db_path=db_path)

    def _must_not_call(sample_texts: list[str], client: Any = None) -> TopicLabelResult:
        raise AssertionError("dry_run không được gọi Claude")

    monkeypatch.setattr(clustering_import, "label_cluster_with_claude", _must_not_call)
    _write_results(results_path, unit_ids, [0, 0, 0, 0])
    stats = clustering_import.run_import(db_path=db_path, dry_run=True)
    assert stats["topic_events"] == {
        "topic_2": "merged",
        "topic_0": "retired",
        "topic_1": "retired",
    }
    assert stats["n_named_now"] == 1
