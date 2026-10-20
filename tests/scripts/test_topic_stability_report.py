"""Test cho `scripts/topic_stability_report.py` — script sinh số liệu của ADR-0024."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts import topic_stability_report as report
from src.analysis.partition_history import distinct_partitions
from src.api.models import PostInsights, ThreadsPost
from src.db.schema import (
    connect,
    create_schema,
    insert_cluster_run,
    insert_insight_snapshot,
    replace_topic_comparisons,
    upsert_post,
)
from src.models.insight_snapshot import InsightSnapshot
from tests.test_main_pipeline import stored_comparison_row


def _run(run_id: int, ari: float | None, labels: dict[str, int]) -> report.ClusterRun:
    return report.ClusterRun(run_id, f"2026-10-{run_id:02d}T10:30:00+00:00", 2, 0.3, ari, labels)


A = {"u1": 0, "u2": 0, "u3": -1}
B = {"u1": 0, "u2": 1, "u3": -1}


def test_script_groups_runs_with_the_shared_partition_definition() -> None:
    # Định nghĩa "cách chia" nằm ở `src/analysis/partition_history.py` (test đầy đủ ở
    # tests/analysis/test_partition_history.py); script phải dùng đúng định nghĩa đó với ClusterRun
    runs = [_run(4, 0.5, B), _run(2, None, A), _run(3, 1.0, A)]

    groups = distinct_partitions(runs)

    assert [[run.id for run in group] for group in groups] == [[2, 3], [4]]


def test_jaccard_and_members() -> None:
    labels = {"a": 0, "b": 0, "c": 1, "d": -1}

    assert report.members(labels, 0) == {"a", "b"}
    assert report.jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)
    assert report.jaccard(set(), set()) == 0.0


def test_noise_units_have_no_group_and_keep_their_snapshot() -> None:
    insights: dict[str, PostInsights | None] = {"a": PostInsights(post_id="a", views=10), "b": None}

    obs = report.observations({"b": -1, "a": 3}, insights)

    assert [(o.unit_id, o.topic_id) for o in obs] == [("a", "c3"), ("b", None)]
    assert obs[0].insights is insights["a"]


def _db(tmp_path: Path) -> Path:
    """13 bài: u0–u5 engagement cao, còn lại thấp. Lần 1–2 cùng cách chia trên u0–u11 (u0–u5 là cụm
    0, còn lại nhiễu); lần 3 có thêm bài mới u12 (nhiễu), tách cụm 0 (u0–u2 giữ, u3–u5 thành nhiễu)
    và gom u6–u11 thành cụm 1 → 12 unit chung ở mọi cách chia."""
    db = tmp_path / "t.db"
    conn = connect(db)
    create_schema(conn)
    units = [f"u{i}" for i in range(13)]
    for i, unit in enumerate(units):
        upsert_post(
            conn,
            ThreadsPost.model_validate(
                {"id": unit, "timestamp": "2026-10-01T10:00:00+0000", "media_type": "TEXT_POST"}
            ),
        )
        likes = 100 + i if i < 6 else 10 + i
        insert_insight_snapshot(
            conn,
            InsightSnapshot(
                post_id=unit,
                fetched_at=datetime(2026, 10, 17, tzinfo=UTC),
                views=1000,
                likes=likes,
                replies=0,
                reposts=0,
                quotes=0,
            ),
        )
    first = {u: (0 if i < 6 else -1) for i, u in enumerate(units[:12])}
    third = {u: (0 if i < 3 else -1 if i < 6 or i == 12 else 1) for i, u in enumerate(units)}
    for day, labels, ari in [(1, first, None), (2, first, 1.0), (3, third, 0.4)]:
        insert_cluster_run(
            conn,
            run_at=f"2026-10-0{day}T10:30:00+00:00",
            model_id="BAAI/bge-m3",
            params={},
            n_units=len(labels),
            n_clusters=len({v for v in labels.values() if v != -1}),
            noise_ratio=sum(v == -1 for v in labels.values()) / len(labels),
            dbcv=None,
            ari_vs_previous=ari,
            labels=labels,
        )
    conn.commit()
    conn.close()
    return db


def test_report_counts_partitions_and_tracks_a_past_cluster(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = _db(tmp_path)

    report.main(
        [
            "--db",
            str(db),
            "--reference-run",
            "1",
            "--reference-cluster",
            "0",
            "--permutations",
            "200",
        ]
    )

    out = capsys.readouterr().out
    assert "1. 3 lần gom cụm = 2 cách chia khác nhau" in out
    assert "lần 1–2" in out and "lần 3–3" in out
    # Chạy lại phép so chỉ trên lần cuối của mỗi cách chia (mục 3 và 4)
    assert "   lần 2:" in out and "   lần 3:" in out and "   lần 1:" not in out
    section_3, rest = out.split("4. Như 3")
    section_4 = rest.split("5. Nhóm bài tham chiếu")[0]
    assert "   lần 3: 13 unit" in section_3
    # Mục 4 bỏ bài mới u12 → cùng tập bài ở mọi cách chia
    assert ", chỉ trên 12 unit có mặt ở mọi cách chia" in section_4
    assert "   lần 3: 12 unit" in section_4
    assert "5. Nhóm bài tham chiếu: cụm c0 của lần 1 (n = 6)" in out
    # Lần 3: 3/6 bài tham chiếu còn ở cụm 0 (3 bài) → Jaccard 3/6; n đo được 3 vs 10
    assert "cụm khớp nhất c0 (3 bài, Jaccard 0.50): c0 engagement: n = 3 vs 10" in out


def test_history_only_prints_k_of_m_like_the_api(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Lần 1–2 cùng cách chia: lần 2 (mới nhất) đại diện, không đạt; lần 3 đạt → cao hơn 1 / m = 2
    db = _db(tmp_path)
    conn = connect(db)
    for run_id, p_holm in [(1, 0.01), (2, 0.30), (3, 0.01)]:
        replace_topic_comparisons(
            conn,
            cluster_run_id=run_id,
            computed_at="2026-10-03T11:00:00+00:00",
            snapshot_as_of=None,
            n_permutations=100,
            random_seed=0,
            holm_family_size=1,
            rows=[stored_comparison_row("topic_1", effect=0.6, p_holm=p_holm)],
        )
    conn.close()

    report.main(["--db", str(db), "--history-only"])

    out = capsys.readouterr().out
    assert "1. " not in out  # không chạy các mục chậm
    assert "2 cách chia có kết quả so sánh (đại diện = lần [2, 3]), từ 2026-10-02" in out
    assert "topic_1 engagement: cao hơn 1, thấp hơn 0 / m = 2 (+0 thiếu bài), từ 2026-10-02" in out


def test_reference_run_without_cluster_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        report.main(["--db", str(_db(tmp_path)), "--reference-run", "1"])


def test_unknown_reference_run_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = _db(tmp_path)

    with pytest.raises(SystemExit):
        report.main(["--db", str(db), "--reference-run", "99", "--reference-cluster", "0"])

    assert "không có lần gom cụm 99" in capsys.readouterr().err


def test_report_without_cluster_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "empty.db"
    conn = connect(db)
    create_schema(conn)
    conn.close()

    report.main(["--db", str(db)])

    assert "Chưa có lần gom cụm nào" in capsys.readouterr().out


def test_history_only_on_a_database_without_tables(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # DB chưa migrate: in "chưa có", không crash (code-reviewer 2026-10-20)
    db = tmp_path / "bare.db"
    connect(db).close()

    report.main(["--db", str(db), "--history-only"])

    assert "Chưa có lần so sánh nào." in capsys.readouterr().out
