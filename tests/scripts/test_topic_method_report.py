"""Test cho `scripts/topic_method_report.py` — script sinh số liệu của ADR-0023."""

import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from scripts import topic_method_report as report
from src.analysis.significance import brunner_munzel_asymptotic, compare_groups
from src.api.models import MediaType, ThreadsPost
from src.db.schema import (
    connect,
    create_schema,
    insert_cluster_run,
    insert_insight_snapshot,
    insert_topic_label_history,
    upsert_content_unit,
    upsert_post,
    upsert_post_topic_label,
    upsert_topic,
)
from src.models.content_unit import ContentUnit
from src.models.insight_snapshot import InsightSnapshot


def test_population_delta_is_zero_without_shift_and_one_beyond_the_range() -> None:
    values = [1.0, 2.0, 3.0, 4.0]

    assert report.population_delta(values, 0.0) == 0.0
    assert report.population_delta(values, 10.0) == 1.0


def test_rejection_rate_counts_nan_as_not_rejected() -> None:
    p_values = np.array([0.01, 0.2, math.nan, 0.04])

    assert report.rejection_rate(p_values) == 0.5


def test_binomial_se_shrinks_with_views() -> None:
    assert report.binomial_se_points(2.0, 400) == pytest.approx(0.7, abs=1e-9)
    assert report.binomial_se_points(2.0, 40_000) == pytest.approx(0.07, abs=1e-9)


def test_runs_keeping_label_counts_only_the_latest_consecutive_kept_runs() -> None:
    events = [
        None,  # lần chạy trước ADR-0018 — chưa ghi sự kiện
        {"topic_0": "relabeled"},
        {"topic_0": "kept"},
        {"topic_0": "kept_semantic"},
    ]

    assert report.runs_keeping_label(events, "topic_0") == 2
    assert report.runs_keeping_label(events, "topic_9") == 0


def test_attainable_level_reflects_permutation_discreteness() -> None:
    # B = 2.000: ở 0.05/27 chỉ p = 2/2001 đạt → 0.10%; ở 0.05 → 100/2001
    assert report.attainable_level(0.05 / 27, 2_000) == pytest.approx(2 / 2001)
    assert report.attainable_level(0.05, 2_000) == pytest.approx(100 / 2001)
    assert report.attainable_level(0.05 / 27, 100_000) == pytest.approx(184 / 100_001)


def test_holm_by_key_skips_undefined_p_values() -> None:
    defined = compare_groups([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], [2.0, 4.0, 6.0, 8.0, 10.0, 12.0])
    tied = compare_groups([2.0] * 5, [2.0] * 5)  # MW: p = NaN khi mọi giá trị trùng nhau
    tests = [
        report.TopicTest("topic_0", "engagement", defined, None),
        report.TopicTest("topic_1", "engagement", tied, None),
    ]

    adjusted = report.holm_by_key(tests, "MW")

    assert tied.p_value_mann_whitney is not None
    assert math.isnan(tied.p_value_mann_whitney)
    assert list(adjusted) == [("topic_0", "engagement")]
    assert adjusted[("topic_0", "engagement")] == defined.p_value_mann_whitney


def test_asymptotic_p_values_fall_back_to_mann_whitney_when_groups_separate() -> None:
    """Hàng 0 tách hẳn nhau (BM-t không xác định) → lấy p Mann-Whitney để hàng đó không bị đếm
    nhầm là "không bác bỏ"; hàng 1 chồng nhau → giữ p BM-t."""
    topic = np.array([[1.0, 2.0, 3.0, 4.0, 5.0], [1.0, 4.0, 6.0, 9.0, 12.0]])
    rest = np.array([[10.0, 11.0, 12.0, 13.0, 14.0, 15.0], [2.0, 3.0, 5.0, 8.0, 10.0, 11.0]])

    bm_t, mann_whitney = report.asymptotic_p_values(topic, rest)

    assert brunner_munzel_asymptotic(topic[0].tolist(), rest[0].tolist()) is None
    assert bm_t[0] == pytest.approx(mann_whitney[0])
    overlapping = brunner_munzel_asymptotic(topic[1].tolist(), rest[1].tolist())
    assert overlapping is not None
    assert bm_t[1] == pytest.approx(overlapping.p_value)


def test_behrens_fisher_shows_mann_whitney_breaking_when_the_small_group_is_wider() -> None:
    """Điều ADR-0023 dựa vào: δ thật = 0 nhưng topic phân tán gấp đôi → Mann-Whitney báo động giả
    rõ hơn 5%, Brunner-Munzel thì không."""
    topic, rest = report.null_behrens_fisher(2.0, 8, 146, 2000, seed=0)

    rates = report.asymptotic_rates(topic, rest, (0.05,))

    assert rates["MW"][0] > 0.09
    assert rates["BM-t"][0] < 0.08


def test_permutation_rates_stay_near_alpha_when_groups_share_a_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hoán vị đúng mức khi 2 nhóm cùng phân phối (đổi nhãn không đổi phân phối) — kiểm thô với ít
    lần mô phỏng; số đầy đủ ở mục 5 của script."""
    monkeypatch.setattr(report, "N_SIM_PERMUTATIONS", 400)
    topic, rest = report.null_behrens_fisher(1.0, 6, 40, 200, seed=1)

    (rate,) = report.permutation_rates(topic, rest, (0.05,), seed=0)

    assert 0.01 <= rate <= 0.10


def _seed(db_path: Path) -> None:
    """2 topic × 6 bài + 6 bài nhiễu, engagement/share/conversation trải khác nhau."""
    conn = connect(db_path)
    create_schema(conn)
    start = datetime(2026, 9, 1, 9, tzinfo=UTC)
    labels: dict[str, int] = {}
    for i in range(18):
        post_id = f"p{i:02d}"
        post = ThreadsPost(
            id=post_id,
            text=f"post {i}",
            timestamp=start + timedelta(days=i),
            media_type=MediaType.TEXT_POST,
        )
        upsert_post(conn, post)
        upsert_content_unit(conn, ContentUnit(root=post, full_text=post.text or ""))
        insert_insight_snapshot(
            conn,
            InsightSnapshot(
                post_id=post_id,
                fetched_at=start + timedelta(days=30),
                views=500 + 400 * i,
                likes=5 + (i * 7) % 23,
                replies=i % 4,
                reposts=i % 3,
                quotes=0,
            ),
        )
        labels[post_id] = 0 if i < 6 else 1 if i < 12 else -1
    for topic_number in (0, 1):
        topic_id = f"topic_{topic_number}"
        upsert_topic(
            conn,
            topic_id=topic_id,
            label_en=f"Topic {topic_number}",
            description_en=None,
            method="cluster",
            labeled_at="2026-10-05T10:30:00+00:00",
        )
        insert_topic_label_history(
            conn,
            topic_id=topic_id,
            label_en=f"Topic {topic_number}",
            description_en=None,
            labeled_at="2026-10-05T10:30:00+00:00",
            label_model="claude-sonnet-5-5",
            label_prompt_version=2,
            reason="config_change",
            sources=[],
        )
    for post_id, label in labels.items():
        if label >= 0:
            upsert_post_topic_label(
                conn, post_id=post_id, topic_id=f"topic_{label}", method="cluster"
            )
    for day, events in ((5, {"topic_0": "relabeled", "topic_1": "relabeled"}), (6, None)):
        insert_cluster_run(
            conn,
            run_at=f"2026-10-0{day}T10:30:00+00:00",
            model_id="BAAI/bge-m3",
            params={},
            n_units=len(labels),
            n_clusters=2,
            noise_ratio=6 / 18,
            dbcv=None,
            ari_vs_previous=None,
            labels=labels,
            topic_events=events or {"topic_0": "kept", "topic_1": "kept"},
        )
    conn.commit()
    conn.close()


def test_report_prints_every_section_on_a_small_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "threads.db"
    _seed(db_path)
    # mô phỏng nhỏ để test nhanh — cấu trúc in ra là thứ được kiểm, không phải con số
    monkeypatch.setattr(report, "N_SIMULATIONS", 40)
    monkeypatch.setattr(report, "N_SIMULATIONS_BOOTSTRAP", 4)
    monkeypatch.setattr(report, "N_BOOTSTRAP", 20)
    monkeypatch.setattr(report, "SHIFT_GRID", (0.0, 5.0, 50.0))
    monkeypatch.setattr(report, "N_REPORT_PERMUTATIONS", 200)
    monkeypatch.setattr(report, "N_SIM_PERM_RUNS", 3)
    monkeypatch.setattr(report, "N_SIM_PERMUTATIONS", 50)
    monkeypatch.setattr(sys, "argv", ["topic_method_report", "--db", str(db_path)])

    report.main()

    out = capsys.readouterr().out
    assert "unit có embedding=18 · nhiễu=6 (33.3%) · trong topic=12 · topic=2" in out
    for section in range(1, 10):
        assert f"=== {section}." in out
    # 3 phương pháp cạnh nhau, mỗi phương pháp 2 họ Holm: cả trang (2 topic × 3 chỉ số) + landing
    for method in ("MW", "BM-t", "BM-perm"):
        assert f"{method:<8} họ 6 (trang Topics):" in out
    assert "họ 2 (chỉ engagement, panel landing):" in out
    assert "BM-perm [" in out
    assert "mức chuẩn ĐẠT ĐƯỢC của cột BM-perm" in out
    assert "p Holm của từng phương pháp (họ 27 / họ 9)" in out
    assert "Sàn P25 =" in out
    assert "lịch sử tên: lý do config_change: 2 dòng" in out
    assert "giữ tên qua 1 lần chạy liên tiếp gần nhất" in out


def test_report_says_so_when_nothing_was_clustered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "threads.db"
    create_schema(connect(db_path))
    monkeypatch.setattr(sys, "argv", ["topic_method_report", "--db", str(db_path)])

    report.main()

    assert "Chưa có lần gom cụm nào" in capsys.readouterr().out
