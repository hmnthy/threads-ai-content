"""Thí nghiệm RQ-01 (`scripts/rq01_seed_stability.py`) — DB giả trong `tmp_path`, bộ gom cụm giả
thay UMAP + HDBSCAN (chỉ có trong WSL2); không đọc data/threads.db thật."""

from __future__ import annotations

import inspect
import json
import shutil
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from scripts import rq01_seed_stability as rq
from src.analysis.topic_stability import ARMS, replicate_positions
from src.api.models import MediaType, ThreadsPost
from src.db.schema import (
    connect,
    content_hash,
    create_schema,
    insert_cluster_run,
    insert_insight_snapshot,
    upsert_content_unit,
    upsert_embedding,
    upsert_post,
    upsert_post_topic_label,
    upsert_topic,
)
from src.models.content_unit import ContentUnit
from src.models.insight_snapshot import InsightSnapshot

MODEL = "BAAI/bge-m3"
PARAMS = {
    "umap_n_components": 3,
    "umap_n_neighbors": 8,
    "hdbscan_min_cluster_size": 4,
    "cluster_selection_method": "leaf",
}
STORED_PARAMS = {**PARAMS, "umap_random_state": 42}
N_PERM = 200
K = 3


def axis_clusterer(matrix: np.ndarray, umap_seed: int) -> rq.Clustering:
    """Bộ gom cụm giả, tất định: cụm = trục có toạ độ lớn nhất, toạ độ < 0.5 → unclustered.
    Không phụ thuộc seed hay thứ tự — kiểm tái lập luôn đạt khi nhãn lưu theo cùng luật."""
    labels = [int(np.argmax(row)) if float(np.max(row)) >= 0.5 else -1 for row in matrix]
    return rq.Clustering(labels=labels, dbcv=0.3, dbcv_relative=0.1)


def _vector(i: int) -> list[float]:
    # 3 nhóm: trục 0 (u00–u07), trục 1 (u08–u15), lẫn (u16–u21, unclustered)
    if i < 8:
        return [0.9, 0.1, 0.0, 0.0]
    if i < 16:
        return [0.1, 0.9, 0.0, 0.0]
    return [0.3, 0.3, 0.3, 0.1]


def seed_db(path: Path, *, n: int = 22, new_unit: bool = True) -> list[str]:
    """Kênh giả: n unit có chữ + 1 unit rỗng; topic_a (trục 0, like cao) / topic_b (trục 1);
    1 lần gom cụm lưu nhãn theo `axis_clusterer`; (tuỳ chọn) 1 bài mới sau lần gom cụm."""
    conn = connect(path)
    create_schema(conn)
    order: list[str] = []
    labels: dict[str, int] = {}
    stored = axis_clusterer(np.array([_vector(i) for i in range(n)]), 42).labels
    # chèn theo thứ tự KHÔNG sắp theo id: thứ tự job = thứ tự chèn (rowid)
    for i in reversed(range(n)):
        uid = f"u{i:02d}"
        _post(conn, uid, text=f"text {uid}", likes=80 + i if i < 8 else 10 + i)
        upsert_embedding(
            conn,
            object_type="content_unit",
            object_id=uid,
            model_id=MODEL,
            text_hash=content_hash(f"text {uid}"),
            vector=_vector(i),
            created_at="2026-11-01T00:00:00+00:00",
        )
        order.append(uid)
        labels[uid] = stored[i]
    _post(conn, "empty", text="   ", likes=5)  # không có chữ → ngoài export
    for topic_id, label in (("topic_a", 0), ("topic_b", 1)):
        upsert_topic(
            conn,
            topic_id=topic_id,
            label_en=topic_id.title(),
            description_en=None,
            method="cluster",
        )
        for uid, unit_label in labels.items():
            if unit_label == label:
                upsert_post_topic_label(conn, post_id=uid, topic_id=topic_id, method="cluster")
    insert_cluster_run(
        conn,
        run_at="2026-11-01T11:30:00+00:00",
        model_id=MODEL,
        params=STORED_PARAMS,
        n_units=n,
        n_clusters=2,
        noise_ratio=sum(1 for x in labels.values() if x == -1) / n,
        dbcv=0.3,
        ari_vs_previous=None,
        labels=labels,
    )
    if new_unit:
        _post(conn, "u_new", text="new after the run", likes=50)
    conn.commit()
    conn.close()
    return order


def _post(conn: Any, uid: str, *, text: str, likes: int) -> None:
    post = ThreadsPost(
        id=uid,
        text=text,
        timestamp=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        media_type=MediaType.TEXT_POST,
    )
    upsert_post(conn, post)
    upsert_content_unit(conn, ContentUnit(root=post, full_text=text))
    insert_insight_snapshot(
        conn,
        InsightSnapshot(
            post_id=uid,
            fetched_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
            views=1000,
            likes=likes,
            replies=0,
            reposts=0,
            quotes=0,
        ),
    )


@pytest.fixture
def frozen(tmp_path: Path) -> tuple[Path, list[str]]:
    source = tmp_path / "source.db"
    order = seed_db(source)
    out = tmp_path / "rq01"
    rq.run_freeze(source, out)
    return out, order


def count_agreement(
    reference: Mapping[str, int], records: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Thay `agreement_summary` (cần scikit-learn) trong bộ test nhanh: chỉ đếm số lần / số cặp —
    scikit-learn chỉ được import ở bước WSL2, Smart App Control có thể chặn nó trên Windows."""
    out: dict[str, Any] = {}
    for arm in ARMS:
        n = sum(1 for r in records if r["arm"] == arm)
        out[arm] = {"vs_reference": {"n": n}, "pairwise": {"n": n * (n - 1) // 2}}
    return out


def _replicate(out: Path, clusterer: rq.Clusterer = axis_clusterer) -> dict[str, Any]:
    return rq.run_replicates(
        out,
        clusterer=clusterer,
        production_params=PARAMS,
        replicates=K,
        agreement=count_agreement,
        log=lambda _: None,
    )


# --- freeze ---------------------------------------------------------------------------------


def test_freeze_records_the_reference_run_and_refuses_a_second_freeze(
    frozen: tuple[Path, list[str]],
) -> None:
    out, _ = frozen
    manifest = json.loads((out / rq.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["reference_cluster_run_id"] == 1
    assert manifest["reference_n_units"] == 22
    assert manifest["latest_snapshot"].startswith("2026-11-01T12:00")
    assert manifest["sha256"] == rq.sha256_file(out / rq.FROZEN_DB)
    with pytest.raises(rq.ExperimentError, match="chỉ làm một lần"):
        rq.run_freeze(out / rq.FROZEN_DB, out)


def test_tampered_frozen_copy_is_rejected(frozen: tuple[Path, list[str]]) -> None:
    out, _ = frozen
    with (out / rq.FROZEN_DB).open("ab") as f:
        f.write(b"\0")
    with pytest.raises(rq.ExperimentError, match="đã đổi sau khi đóng băng"):
        _replicate(out)


def test_manifest_without_hash_stops_as_an_experiment_error(
    frozen: tuple[Path, list[str]],
) -> None:
    out, _ = frozen
    (out / rq.MANIFEST).write_text("{}", encoding="utf-8")
    with pytest.raises(rq.ExperimentError, match="không có sha256"):
        _replicate(out)


def test_code_identity_follows_the_import_graph_not_a_hand_written_list() -> None:
    compare = rq.module_files(rq.COMPARE_CODE)
    # file định nghĩa chỉ số + cờ mẫu nhỏ — danh sách viết tay trước đây đã bỏ sót
    for needed in (
        "src/analysis/significance.py",
        "src/analysis/share_rate.py",
        "src/analysis/conversation.py",
        "src/analysis/engagement.py",
        "src/api/models.py",
        "src/pipeline/compare_topics.py",
    ):
        assert needed in compare
    replicate = rq.module_files(rq.REPLICATE_CODE)
    for needed in (
        "scripts/rq01_seed_stability.py",
        "src/analysis/topic_stability.py",
        "src/nlp/topics.py",  # import trong hàm
        "src/pipeline/cluster_wsl.py",
        "src/nlp/topic_profile.py",  # ARI của agreement.json
    ):
        assert needed in replicate
    assert all(not f.startswith(("tests/", "src/dashboard/")) for f in replicate)


# --- replicates -----------------------------------------------------------------------------


def test_reference_order_keeps_job_order_and_filters_empty_and_new_units() -> None:
    units = [("b", "x"), ("new", "y"), ("a", "x"), ("empty", "  "), ("c", None)]
    order, n_new = rq.reference_order(units, {"a": 0, "b": -1})
    assert order == ["b", "a"]  # thứ tự đầu vào, không sắp lại
    assert n_new == 1  # "new" có chữ nhưng sau lần tham chiếu; bài rỗng không đếm
    with pytest.raises(rq.ExperimentError, match="không còn trong content_units"):
        rq.reference_order(units, {"a": 0, "gone": 1})


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ([0, 0, 1, -1], [5, 5, 2, -1], True),  # chỉ khác cách đánh số
        ([0, 0, 1, -1], [0, 0, 1, 1], False),  # unclustered ↔ cụm
        ([0, 0, 1, 1], [0, 0, 0, 0], False),  # gộp
        ([0, 0, 0, 0], [0, 0, 1, 1], False),  # tách
        ([0, 1], [0, 1, 1], False),
    ],
)
def test_same_partition_allows_only_renumbering(a: list[int], b: list[int], same: bool) -> None:
    assert rq.same_partition(a, b) is same


def test_reproducibility_passes_then_replicates_follow_the_preregistered_inputs(
    frozen: tuple[Path, list[str]],
) -> None:
    out, order = frozen
    seeds: list[int] = []

    def recording(matrix: np.ndarray, seed: int) -> rq.Clustering:
        seeds.append(seed)
        return axis_clusterer(matrix, seed)

    report = _replicate(out, recording)
    assert report["passed"] and report["identical_numbering"]
    assert report["n_units"] == 22 and report["n_new_units_filtered"] == 1
    assert report["n_vector_hash_mismatch"] == 0
    assert seeds[0] == 42  # kiểm tái lập chạy TRƯỚC, bằng seed đã lưu
    assert sorted(seeds[1:]) == sorted([b for b in range(1, K + 1) for _ in ARMS])
    records = rq.read_jsonl(out / rq.REPLICATES)
    assert len(records) == K * len(ARMS)
    for r in records:
        positions = replicate_positions(len(order), r["b"], r["arm"])
        assert r["order"] == [order[i] for i in positions]  # thứ tự job, rồi hoán vị lần b
        assert r["umap_seed"] == r["b"]
        assert list(r["labels"]) == r["order"]
    p1 = next(r for r in records if r["arm"] == "P" and r["b"] == 1)
    s1 = next(r for r in records if r["arm"] == "S" and r["b"] == 1)
    assert len(s1["order"]) == 22 and len(p1["order"]) == 22 - 1  # ⌈3% · 22⌉ = 1
    assert s1["order"][: len(p1["order"])] == p1["order"]


def test_replicates_resume_without_redoing_finished_runs(frozen: tuple[Path, list[str]]) -> None:
    out, _ = frozen
    _replicate(out)
    lines = (out / rq.REPLICATES).read_text(encoding="utf-8").splitlines()
    # máy ngủ giữa chừng: 2 dòng đủ + 1 dòng ghi dở
    (out / rq.REPLICATES).write_text("\n".join(lines[:2]) + "\n" + lines[2][:30], encoding="utf-8")
    calls: list[int] = []

    def counting(matrix: np.ndarray, seed: int) -> rq.Clustering:
        calls.append(seed)
        return axis_clusterer(matrix, seed)

    _replicate(out, counting)
    assert len(calls) == 1 + (K * len(ARMS) - 2)  # kiểm tái lập + các lần còn thiếu
    again = rq.read_jsonl(out / rq.REPLICATES)
    assert sorted((r["arm"], r["b"]) for r in again) == sorted(
        (arm, b) for arm in ARMS for b in range(1, K + 1)
    )


def test_failed_reproducibility_stops_before_any_replicate(frozen: tuple[Path, list[str]]) -> None:
    out, _ = frozen

    def shifted(matrix: np.ndarray, seed: int) -> rq.Clustering:
        result = axis_clusterer(matrix, seed)
        return rq.Clustering([0 for _ in result.labels], result.dbcv, result.dbcv_relative)

    with pytest.raises(rq.ExperimentError, match="kiểm tái lập thất bại"):
        _replicate(out, shifted)
    report = json.loads((out / rq.REPRODUCIBILITY).read_text(encoding="utf-8"))
    assert report["passed"] is False and "versions" in report
    assert not (out / rq.REPLICATES).exists()


def test_reference_params_different_from_production_stop(frozen: tuple[Path, list[str]]) -> None:
    out, _ = frozen
    with pytest.raises(rq.ExperimentError, match="tham số"):
        rq.run_replicates(
            out,
            clusterer=axis_clusterer,
            production_params={**PARAMS, "umap_n_neighbors": 10},
            replicates=K,
            log=lambda _: None,
        )


def test_read_jsonl_rejects_a_corrupt_line_in_the_middle(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    path.write_text('{"a": 1}\nnot json\n{"a": 2}\n', encoding="utf-8")
    with pytest.raises(rq.ExperimentError, match="hỏng giữa file"):
        rq.read_jsonl(path)


def test_only_the_owning_step_repairs_a_jsonl_file(tmp_path: Path) -> None:
    path = tmp_path / "x.jsonl"
    being_written = '{"a": 1}\n{"a": 2'  # bước khác đang ghi dở dòng 2
    path.write_text(being_written, encoding="utf-8")
    assert rq.read_jsonl(path) == [{"a": 1}]
    assert path.read_text(encoding="utf-8") == being_written  # người đọc không đụng file
    assert rq.read_jsonl(path, repair=True) == [{"a": 1}]
    assert rq.read_jsonl(path) == [{"a": 1}] and '{"a": 2' not in path.read_text("utf-8")
    # dòng cuối hợp lệ nhưng thiếu \n: sửa thì thêm \n, để lần ghi nối sau không dính dòng
    path.write_text('{"a": 1}', encoding="utf-8")
    rq.read_jsonl(path, repair=True)
    rq._append_jsonl(path, {"a": 3})
    assert rq.read_jsonl(path) == [{"a": 1}, {"a": 3}]


def test_replicates_from_another_freeze_or_library_version_stop(
    frozen: tuple[Path, list[str]],
) -> None:
    out, _ = frozen
    _replicate(out)
    path = out / rq.REPLICATES
    records = rq.read_jsonl(path)
    original = path.read_text(encoding="utf-8")
    other_freeze = [{**records[0], "frozen_sha256": "x"}, *records[1:]]
    path.write_text("".join(json.dumps(r) + "\n" for r in other_freeze), encoding="utf-8")
    with pytest.raises(rq.ExperimentError, match="bản đóng băng khác"):
        _replicate(out)
    with pytest.raises(rq.ExperimentError, match="bản đóng băng khác"):
        _evaluate(out)
    other_venv = [{**records[0], "versions": {"umap-learn": "0.0"}}, *records[1:]]
    path.write_text("".join(json.dumps(r) + "\n" for r in other_venv), encoding="utf-8")
    report_before = (out / rq.REPRODUCIBILITY).read_text(encoding="utf-8")
    with pytest.raises(rq.ExperimentError, match="phiên bản thư viện khác"):
        _replicate(out)
    with pytest.raises(rq.ExperimentError, match="phiên bản thư viện khác"):
        rq.run_replicates(
            out,
            clusterer=axis_clusterer,
            production_params=PARAMS,
            check_only=True,
            agreement=count_agreement,
            log=lambda _: None,
        )
    # lần bị từ chối không đè báo cáo tái lập của lần đã chấp nhận
    assert (out / rq.REPRODUCIBILITY).read_text(encoding="utf-8") == report_before
    with pytest.raises(rq.ExperimentError, match="phiên bản khác lần kiểm tái lập"):
        _evaluate(out)
    path.write_text(original, encoding="utf-8")


def test_replicates_write_partition_agreement_for_evaluate(
    frozen: tuple[Path, list[str]],
) -> None:
    out, _ = frozen
    _replicate(out)
    agreement = json.loads((out / rq.AGREEMENT).read_text(encoding="utf-8"))
    records = rq.read_jsonl(out / rq.REPLICATES)
    assert agreement["labels_sha256"] == {
        f"{r['arm']}:{r['b']}": r["labels_sha256"] for r in records
    }
    assert agreement["arms"]["P"]["pairwise"]["n"] == K * (K - 1) // 2  # nhận đủ mọi lần
    assert agreement["arms"]["S"]["vs_reference"]["n"] == K
    # agreement.json lệch replicates.jsonl (VD bước replicates chưa chạy xong lần cuối) → dừng
    for key, stale in (
        ("labels_sha256", {**agreement["labels_sha256"], "P:1": "x"}),
        ("code_sha256", "code cũ"),
    ):
        (out / rq.AGREEMENT).write_text(json.dumps({**agreement, key: stale}), encoding="utf-8")
        with pytest.raises(rq.ExperimentError, match="không khớp"):
            _evaluate(out)


def test_compare_digest_covers_the_comparison_helpers_in_the_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = rq.compare_code_digest()
    real = inspect.getsource
    monkeypatch.setattr(
        inspect,
        "getsource",
        lambda f: real(f) + "# sửa" if f is rq.replicate_units else real(f),
    )
    assert rq.compare_code_digest() != before


def test_labels_edited_after_writing_are_rejected(frozen: tuple[Path, list[str]]) -> None:
    out, _ = frozen
    _replicate(out)
    path = out / rq.REPLICATES
    records = rq.read_jsonl(path)
    first = next(iter(records[0]["labels"]))
    records[0]["labels"][first] = 7
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    with pytest.raises(rq.ExperimentError, match="bị đổi sau khi ghi"):
        _evaluate(out)


def test_missing_reference_seed_stops_as_an_experiment_error(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    seed_db(source)
    conn = connect(source)
    conn.execute("UPDATE cluster_runs SET params_json = ?", (json.dumps(PARAMS),))
    conn.commit()
    conn.close()
    rq.run_freeze(source, tmp_path / "rq01")
    with pytest.raises(rq.ExperimentError, match="umap_random_state"):
        _replicate(tmp_path / "rq01")


# --- evaluate -------------------------------------------------------------------------------


def _evaluate(out: Path, workers: int = 1) -> dict[str, Any]:
    return rq.run_evaluate(
        out, workers=workers, n_permutations=N_PERM, replicates=K, log=lambda _: None
    )


def test_evaluate_end_to_end_and_results_do_not_depend_on_workers(
    frozen: tuple[Path, list[str]], tmp_path: Path
) -> None:
    out, _ = frozen
    _replicate(out)
    twin = tmp_path / "twin"
    shutil.copytree(out, twin)
    serial = _evaluate(out)
    parallel = _evaluate(twin, workers=2)
    assert serial["arms"] == parallel["arms"]
    ref = serial["reference"]
    assert ref["n_units"] == 22 and ref["n_topics"] == 2
    assert ref["holm_family_size"] == 6  # 2 topic × 3 chỉ số
    assert ref["topic_names"] == {"topic_a": "Topic_A", "topic_b": "Topic_B"}
    # bộ gom cụm giả không đổi theo seed/thứ tự: mọi topic sống ở mọi lần, J = 1
    for arm in ARMS:
        stability = serial["arms"][arm]["topic_stability"]
        assert stability["topic_a"]["alive"] == K
        assert serial["arms"][arm]["vs_reference"]["n"] == K  # ghép từ agreement.json
        assert serial["arms"][arm]["pairwise"]["n"] == K * (K - 1) // 2
    assert serial["arms"]["S"]["topic_stability"]["topic_a"]["mean_jaccard"] == 1.0
    saved = json.loads((out / rq.EVALUATION).read_text(encoding="utf-8"))
    assert saved["frozen_sha256"] == serial["frozen_sha256"]
    assert saved["code_sha256"] == {
        "replicates": rq.code_digest(rq.REPLICATE_CODE),
        "compare": rq.compare_code_digest(),
    }
    # 2. lần: phép so đã có trong comparisons.jsonl, không chạy lại
    lines = len(rq.read_jsonl(out / rq.COMPARISONS))
    _evaluate(out)
    assert len(rq.read_jsonl(out / rq.COMPARISONS)) == lines == K * len(ARMS)


def test_evaluate_refuses_without_a_passed_reproducibility_check(
    frozen: tuple[Path, list[str]],
) -> None:
    out, _ = frozen
    with pytest.raises(rq.ExperimentError, match="không đọc được reproducibility.json"):
        _evaluate(out)
    (out / rq.REPRODUCIBILITY).write_text(json.dumps({"passed": False}), encoding="utf-8")
    with pytest.raises(rq.ExperimentError, match="kiểm tái lập"):
        _evaluate(out)


def test_evaluate_rejects_comparisons_from_another_permutation_count(
    frozen: tuple[Path, list[str]],
) -> None:
    out, _ = frozen
    _replicate(out)
    _evaluate(out)
    with pytest.raises(rq.ExperimentError, match="lần chạy khác"):
        rq.run_evaluate(out, n_permutations=N_PERM + 1, replicates=K, log=lambda _: None)


def test_cached_comparison_is_not_reused_for_different_labels(
    frozen: tuple[Path, list[str]],
) -> None:
    out, _ = frozen
    _replicate(out)
    _evaluate(out)
    # gom lại ra nhãn khác cho P b=1 (replicates + agreement nhất quán với nhau), nhưng
    # comparisons.jsonl cũ vẫn còn
    path = out / rq.REPLICATES
    records = rq.read_jsonl(path)
    agreement = json.loads((out / rq.AGREEMENT).read_text(encoding="utf-8"))
    for r in records:
        if r["arm"] == "P" and r["b"] == 1:
            first = next(iter(r["labels"]))
            r["labels"][first] = 7  # nhãn chưa từng có → chắc chắn khác (−1 có thể trùng)
            r["labels_sha256"] = rq.labels_digest(r["labels"])
            agreement["labels_sha256"]["P:1"] = r["labels_sha256"]
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    (out / rq.AGREEMENT).write_text(json.dumps(agreement), encoding="utf-8")
    with pytest.raises(rq.ExperimentError, match="tính trên nhãn khác"):
        _evaluate(out)


def test_evaluate_resumes_after_a_half_written_comparison_line(
    frozen: tuple[Path, list[str]],
) -> None:
    out, _ = frozen
    _replicate(out)
    _evaluate(out)
    path = out / rq.COMPARISONS
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n" + lines[-1][:40], encoding="utf-8")
    again = _evaluate(out)
    assert len(rq.read_jsonl(path)) == K * len(ARMS)
    assert again["arms"]["P"]["topic_stability"]["topic_a"]["alive"] == K


def test_evaluate_stops_when_topic_labels_and_stored_labels_disagree(
    frozen: tuple[Path, list[str]], tmp_path: Path
) -> None:
    out, _ = frozen
    _replicate(out)
    # bản đóng băng khác: 1 unit của topic_a bị gán sang topic_b trong post_topic_labels
    source = tmp_path / "drifted.db"
    seed_db(source)
    conn = connect(source)
    conn.execute("UPDATE post_topic_labels SET topic_id = 'topic_b' WHERE post_id = 'u00'")
    conn.commit()
    conn.close()
    drifted = tmp_path / "drifted"
    rq.run_freeze(source, drifted)
    _replicate(drifted)
    with pytest.raises(rq.ExperimentError, match="không cùng một cách chia"):
        _evaluate(drifted)


# --- summarise: tỉ lệ giữ, mẫu số, kết luận mới (dữ liệu giả viết tay) -----------------------

REF_TOPICS = {"t1": ["a", "b", "c", "d"], "t2": ["e", "f", "g", "h"]}
REF_LABELS = {"a": 0, "b": 0, "c": 0, "d": 0, "e": 1, "f": 1, "g": 1, "h": 1, "z": -1}
T1_KEEP = {"a": 0, "b": 0, "c": 0, "d": 0, "e": 1, "f": 1, "g": 1, "h": 1, "z": -1}


def _row(group: str, metric: str, p: float | None, d: float | None, few: bool = False) -> Any:
    return {
        "group_id": group,
        "metric": metric,
        "p_value_holm": p,
        "effect_size": d,
        "insufficient_data": few,
    }


def _summarise(
    labels_by_b: Sequence[Mapping[str, int]],
    rows_by_b: Sequence[list[dict[str, Any]]],
    reference_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    records = [
        {"arm": arm, "b": b + 1, "labels": dict(labels), "n_clusters": 2, "noise_ratio": 0.1}
        | {"dbcv": None if b == 0 else 0.2}
        for arm in ARMS
        for b, labels in enumerate(labels_by_b)
    ]
    comparisons: dict[tuple[str, int], Mapping[str, Any]] = {
        (arm, b + 1): {"rows": rows} for arm in ARMS for b, rows in enumerate(rows_by_b)
    }
    return rq.summarise(
        REF_LABELS,
        REF_TOPICS,
        reference_rows or [_row("t1", "engagement", 0.01, 0.6)],
        records,
        comparisons,
        replicates=len(labels_by_b),
    )


def test_keep_rate_denominator_is_always_k_and_every_miss_counts_as_not_kept() -> None:
    dissolved = {u: -1 for u in REF_LABELS}  # không cụm nào
    labels = [T1_KEEP, dissolved, T1_KEEP, T1_KEEP]
    rows = [
        [_row("c0", "engagement", 0.01, 0.5)],  # giữ higher
        [],  # topic không còn sống
        [_row("c0", "engagement", 0.01, 0.5, few=True)],  # cờ mẫu nhỏ
        [_row("c0", "engagement", 0.01, 0.0)],  # δ = 0 (verdict "lower") — không giữ hướng nào
    ]
    summary = _summarise(labels, rows)
    entry = next(
        c
        for c in summary["arms"]["P"]["conclusions"]
        if c["topic"] == "t1" and c["metric"] == "engagement"
    )
    assert entry["reference_verdict"] == "higher"
    assert entry["higher"]["kept"] == 1 and entry["higher"]["rate"] == 0.25  # 1 / K, không 1 / 3
    assert entry["lower"]["kept"] == 0
    assert entry["matched_verdicts"] == {
        "higher": 1,
        "topic not found": 1,
        "too few posts": 1,
        "lower": 1,
    }
    assert entry["passes_rule"] is False
    assert summary["arms"]["P"]["topic_stability"]["t1"] == {
        "mean_jaccard": 0.75,  # (1 + 0 + 1 + 1) / 4
        "alive": 3,
        "n_reference_units": 4,
    }
    # dòng không có trong phép so (topic t2 không có dòng ở lần nào) → "not tested", không giữ
    t2 = next(
        c
        for c in summary["arms"]["S"]["conclusions"]
        if c["topic"] == "t2" and c["metric"] == "share_rate"
    )
    assert t2["matched_verdicts"]["not tested"] == 3 and t2["higher"]["kept"] == 0
    assert "passes_rule" not in t2  # luật chỉ áp ở nhánh P
    assert summary["arms"]["P"]["dbcv_validity_index"]["n_missing"] == 1


def test_rule_passes_at_75_percent_and_sensitivity_is_reported_separately() -> None:
    labels = [T1_KEEP] * 4
    rows = [[_row("c0", "engagement", 0.01, 0.5)]] * 3 + [[]]
    entry = next(
        c
        for c in _summarise(labels, rows)["arms"]["P"]["conclusions"]
        if c["topic"] == "t1" and c["metric"] == "engagement"
    )
    assert entry["higher"]["kept"] == 3
    assert entry["passes_rule"] is True  # 3/4 = 75%
    assert entry["sensitivity"] == {"60": True, "90": False}
    assert entry["higher"]["ci_contains_threshold"] is True


def test_reference_without_a_verdict_never_passes_even_if_always_kept() -> None:
    labels = [T1_KEEP] * 4
    rows = [[_row("c0", "engagement", 0.01, 0.5)]] * 4
    reference = [_row("t1", "engagement", 0.2, 0.6)]  # tham chiếu: not distinguishable
    entry = next(
        c
        for c in _summarise(labels, rows, reference)["arms"]["P"]["conclusions"]
        if c["topic"] == "t1" and c["metric"] == "engagement"
    )
    assert entry["higher"]["kept"] == 4 and entry["passes_rule"] is False


def test_new_conclusions_count_verdicts_and_those_in_unmatched_clusters() -> None:
    split = {"a": 0, "b": 0, "c": 2, "d": 2, "e": 1, "f": 1, "g": 1, "h": 1, "z": -1}
    labels = [T1_KEEP, split]
    rows = [
        [_row("c0", "engagement", 0.01, 0.5), _row("c1", "share_rate", 0.3, 0.1)],
        # t1 tách đôi: J(t1, c0) = J(t1, c2) = 0.5 → không cụm nào khớp t1
        [_row("c0", "engagement", 0.01, 0.5), _row("c2", "conversation", 0.02, -0.4)],
    ]
    p = _summarise(labels, rows)["arms"]["P"]
    assert p["new_conclusions"]["median"] == 1.5  # 1 rồi 2 kết luận
    assert p["new_conclusions_in_unmatched_clusters"]["median"] == 1.0  # 0 rồi 2


def test_summarise_requires_every_replicate_and_comparison() -> None:
    with pytest.raises(rq.ExperimentError, match="cần đủ"):
        rq.summarise(REF_LABELS, REF_TOPICS, [], [], {}, replicates=2)
    records = [{"arm": arm, "b": b, "labels": T1_KEEP} for arm in ARMS for b in (1, 2)]
    with pytest.raises(rq.ExperimentError, match="thiếu phép so"):
        rq.summarise(REF_LABELS, REF_TOPICS, [], records, {}, replicates=2)


def test_code_change_between_runs_invalidates_only_the_matching_cache(
    frozen: tuple[Path, list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    out, _ = frozen
    _replicate(out)
    _evaluate(out)
    real = rq.code_digest
    # engine kiểm định đổi → phép so cũ không được dùng lại
    monkeypatch.setattr(
        rq, "code_digest", lambda paths: "x" if paths == rq.COMPARE_CODE else real(paths)
    )
    with pytest.raises(rq.ExperimentError, match="lần chạy khác"):
        _evaluate(out)
    _replicate(out)  # khoá của replicates là digest riêng của nó, không phải digest so sánh
    # code gom cụm đổi → replicates cũ không được chạy tiếp, evaluate cũng từ chối
    monkeypatch.setattr(
        rq, "code_digest", lambda paths: "x" if paths == rq.REPLICATE_CODE else real(paths)
    )
    with pytest.raises(rq.ExperimentError, match="code khác"):
        _replicate(out)
    with pytest.raises(rq.ExperimentError, match="code khác"):
        _evaluate(out)


def test_agreement_summary_on_real_scikit_learn() -> None:
    # Smart App Control chặn DLL → ImportError thường (không phải ModuleNotFoundError): phải truyền
    # exc_type thì mới skip (như tests/nlp/test_topics.py); CI Linux vẫn chạy
    pytest.importorskip("sklearn", reason="blocked by Smart App Control", exc_type=ImportError)
    ref = {"a": 0, "b": 0, "c": 1, "d": 1, "e": -1}
    records = [
        {"arm": arm, "b": b, "labels": {"a": 5, "b": 5, "c": 2, "d": 2, "e": -1}}
        for arm in ARMS
        for b in (1, 2, 3)
    ]
    summary = rq.agreement_summary(ref, records)
    for arm in ARMS:
        assert summary[arm]["vs_reference"]["ami_all"]["n"] == 3
        assert summary[arm]["vs_reference"]["ami_all"]["median"] == pytest.approx(1.0)
        assert summary[arm]["pairwise"]["ari_clustered"]["n"] == 3  # 3 cặp (b, b′)


def test_partition_agreement_two_ways_on_common_units() -> None:
    pytest.importorskip("sklearn", reason="blocked by Smart App Control", exc_type=ImportError)
    ref = {"a": 0, "b": 0, "c": 1, "d": 1, "e": -1, "f": -1}
    renumbered = {"a": 7, "b": 7, "c": 3, "d": 3, "e": -1, "f": -1, "new": 0}
    same = rq.partition_agreement(ref, renumbered)
    assert same == {
        "ami_all": pytest.approx(1.0),
        "ari_all": pytest.approx(1.0),
        "ami_clustered": pytest.approx(1.0),
        "ari_clustered": pytest.approx(1.0),
    }
    # e, f từ unclustered vào cụm của a, b: (a) đổi, (b) chỉ trên bài có cụm cả 2 lần — không đổi
    moved = rq.partition_agreement(ref, {"a": 0, "b": 0, "c": 1, "d": 1, "e": 0, "f": 0})
    assert moved["ari_all"] is not None and moved["ari_all"] < 1.0
    assert moved["ari_clustered"] == pytest.approx(1.0)
    assert rq.partition_agreement({"a": 0}, {"a": 0})["ami_all"] is None  # < 2 unit chung


def test_main_needs_a_source_to_freeze_and_reports_experiment_errors(
    frozen: tuple[Path, list[str]], capsys: pytest.CaptureFixture[str]
) -> None:
    out, _ = frozen
    with pytest.raises(SystemExit):
        rq.main(["freeze", "--out-dir", str(out)])
    assert rq.main(["freeze", "--source", str(out / rq.FROZEN_DB), "--out-dir", str(out)]) == 2
    assert "DỪNG" in capsys.readouterr().err
