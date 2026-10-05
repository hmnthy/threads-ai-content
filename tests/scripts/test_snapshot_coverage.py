"""Test độ phủ snapshot (`scripts/snapshot_coverage.py`, ADR-0017) — DB tạm, không chạm DB thật."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from scripts import snapshot_coverage as sc
from src.db.schema import create_schema

T0 = datetime(2026, 10, 1, 11, 15, tzinfo=UTC)  # 13:15 giờ Paris (CEST)


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    return conn


def _post(
    conn: sqlite3.Connection, post_id: str, posted: datetime, role: str | None = None
) -> None:
    conn.execute(
        "INSERT INTO posts (id, timestamp, media_type, is_reply, raw_json, reply_role) "
        "VALUES (?, ?, 'TEXT_POST', ?, '{}', ?)",
        (post_id, posted.isoformat(), 0 if role is None else 1, role),
    )


def _snap(conn: sqlite3.Connection, post_id: str, at: datetime) -> None:
    conn.execute(
        "INSERT INTO insights_snapshots (post_id, fetched_at, views, likes, replies, reposts, "
        "quotes) VALUES (?, ?, 0, 0, 0, 0, 0)",
        (post_id, at.isoformat()),
    )


def test_rows_within_one_run_form_one_batch() -> None:
    times = [T0, T0 + timedelta(minutes=1), T0 + timedelta(minutes=2), T0 + timedelta(hours=4)]
    assert sc.batch_starts(times) == [T0, T0 + timedelta(hours=4)]


def test_coverage_counts_batches_gaps_hours_and_first_day_points() -> None:
    conn = _db()
    _post(conn, "a", T0 - timedelta(hours=1))
    _post(conn, "r", T0 - timedelta(hours=1), role="author_answer")  # reply: không tính
    _post(conn, "young", T0 + timedelta(hours=30))  # chưa đủ 24h tuổi lúc `now`: không tính
    # Lượt 13:15 Paris (mỗi bài 1 dòng, ghi trong ~1 phút) → 17:15 → trống đêm 16h → 09:15
    _snap(conn, "a", T0)
    _snap(conn, "r", T0 + timedelta(minutes=1))
    _snap(conn, "a", T0 + timedelta(hours=4))
    _snap(conn, "a", T0 + timedelta(hours=20))
    _snap(conn, "r", T0 + timedelta(hours=20))
    _snap(conn, "a", T0 + timedelta(hours=24))  # ngoài 24h đầu của "a" (đăng T0 - 1h)
    now = T0 + timedelta(hours=40)

    c = sc.coverage(conn, since=T0 - timedelta(hours=2), now=now)

    assert c.n_batches == 4
    assert c.batches_by_paris_hour == {9: 1, 13: 2, 17: 1}
    assert c.n_long_gaps == 1 and c.median_long_gap_hours == 16.0
    # "a": snapshot lúc +1h, +5h, +21h sau khi đăng; lúc +25h nằm ngoài cửa sổ
    assert c.n_posts_24h == 1 and c.points_first_24h == [3]


def test_overlapping_runs_count_once_per_post_and_show_as_smallest_batch() -> None:
    # Thật 2026-09-21: 2 lượt chạy chồng ghi 2 dòng cho cùng bài cách nhau ~1,5 phút
    conn = _db()
    _post(conn, "a", T0 - timedelta(hours=1))
    _snap(conn, "a", T0)
    _snap(conn, "a", T0 + timedelta(seconds=90))
    _snap(conn, "a", T0 + timedelta(hours=4))
    _snap(conn, "a", T0 + timedelta(hours=14))  # lượt bị đóng băng: chỉ 1 dòng

    c = sc.coverage(conn, since=T0 - timedelta(hours=2), now=T0 + timedelta(hours=30))

    assert c.points_first_24h == [3]  # 3 lượt, không phải 4 dòng
    assert c.smallest_batches[0][1] == 1


def test_paris_since_is_compared_in_utc() -> None:
    # Mốc 2026-10-01 00:00 Paris = 2026-09-30 22:00 UTC: dòng 23:30 UTC hôm trước PHẢI được tính
    conn = _db()
    since = datetime(2026, 10, 1, tzinfo=sc.PARIS)
    _snap(conn, "a", datetime(2026, 9, 30, 23, 30, tzinfo=UTC))
    c = sc.coverage(conn, since=since, now=since + timedelta(days=1))
    assert c.n_batches == 1


def test_empty_db_does_not_crash() -> None:
    c = sc.coverage(_db(), since=T0, now=T0 + timedelta(days=1))
    assert c.n_batches == 0 and c.median_long_gap_hours is None and c.points_first_24h == []
