"""Smoke test cho `scripts/reach_report.py` — script sinh số liệu của ADR-0012."""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts import reach_report
from src.api.models import MediaType, ThreadsPost
from src.db.schema import (
    connect,
    create_schema,
    insert_insight_snapshot,
    upsert_content_unit,
    upsert_post,
)
from src.models.content_unit import ContentUnit
from src.models.insight_snapshot import InsightSnapshot


def _seed(db_path: Path, n_posts: int, sparse_first: int = 0) -> None:
    """`sparse_first` bài đầu cách nhau 30 ngày (kênh đăng thưa), phần còn lại cách 2 ngày."""
    conn = connect(db_path)
    create_schema(conn)
    start = datetime(2025 if sparse_first else 2026, 3 if sparse_first else 5, 1, 9, tzinfo=UTC)
    for i in range(n_posts):
        offset = 30 * min(i, sparse_first) + 2 * max(0, i - sparse_first)
        post = ThreadsPost(
            id=f"p{i:02d}",
            text=f"post {i}",
            timestamp=start + timedelta(days=offset),
            media_type=MediaType.TEXT_POST,
        )
        upsert_post(conn, post)
        upsert_content_unit(conn, ContentUnit(root=post, full_text=post.text or ""))
        views = 1000 + 997 * i % 7000  # trải views để có đủ 3 tầng
        likes = 10 + (i * 13) % 40
        for fetched, value in (
            (post.timestamp + timedelta(hours=3), views // 2),
            (post.timestamp + timedelta(hours=20), views),
            (datetime(2026, 10, 1, tzinfo=UTC), views),
        ):
            insert_insight_snapshot(
                conn,
                InsightSnapshot(
                    post_id=post.id,
                    fetched_at=fetched,
                    views=value,
                    likes=likes,
                    replies=0,
                    reposts=0,
                    quotes=0,
                ),
            )
    conn.commit()
    conn.close()


def test_reach_report_prints_every_adr_number_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "test.db"
    _seed(db_path, n_posts=40)
    monkeypatch.setattr(sys, "argv", ["reach_report", "--db", str(db_path)])

    reach_report.main()

    out = capsys.readouterr().out
    assert "measurable root posts n=40" in out
    for section in (
        "maturity: P90 time-to-90%",
        "P50 relative reach",
        "raw-views tiers",
        "Spearman(raw views, age)",
        "engagement top_20 vs below_median",
        "p Holm (2 comparisons)",
        "window=10 (min_prior=10)",
        "window=30 (min_prior=10)",
        "baseline span (up to 20 prior posts)",
    ):
        assert section in out


def test_reach_report_stops_early_on_too_few_posts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "test.db"
    _seed(db_path, n_posts=2)
    monkeypatch.setattr(sys, "argv", ["reach_report", "--db", str(db_path)])

    reach_report.main()

    assert "dừng" in capsys.readouterr().out


def test_reach_report_counts_posts_whose_baseline_spans_over_90_days(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # 12 bài đầu cách 30 ngày: các bài thứ 10…~23 có mốc trải > 90 ngày
    db_path = tmp_path / "test.db"
    _seed(db_path, n_posts=40, sparse_first=12)
    monkeypatch.setattr(sys, "argv", ["reach_report", "--db", str(db_path)])

    reach_report.main()

    out = capsys.readouterr().out
    line = next(x for x in out.splitlines() if x.startswith("baseline span"))
    assert "span > 90d: 0/" not in line
    assert "those posts were published" in out
