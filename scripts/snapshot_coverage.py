"""Độ phủ của chuỗi snapshot insight — nguồn số liệu cho mục "Giới hạn lấy mẫu" (ADR-0017).

Chạy: `uv run python -m scripts.snapshot_coverage [--since 2026-09-10]`

Số liệu về độ phủ dữ liệu trong ADR/docs phải lấy từ script tái lập được, kèm n — không
ước lượng tay (bài học 2026-10-04: "8 đợt" thật ra là đếm theo phút, "~4 điểm/24h" là đoán).

Định nghĩa:
- 1 **lượt** snapshot = các dòng `insights_snapshots` có `fetched_at` cách dòng trước
  < `BATCH_GAP` (1 lượt chạy ~2 phút ghi 150 dòng).
- **Khoảng trống** = thời gian giữa 2 lượt liên tiếp.
- **Điểm trong 24h đầu** = số LƯỢT (không phải số dòng — 2 lượt chạy chồng có thể ghi 2 dòng cho
  cùng bài cách nhau ~1 phút) có snapshot của 1 root post trong [đăng, đăng + 24h); chỉ tính bài
  đăng sau `since` và đã đủ 24h tuổi.
- **Lượt nhỏ nhất** = các lượt ít dòng nhất (lượt bị đóng băng giữa chừng chỉ ghi vài dòng) — in ra
  để người đọc tự đánh giá, không lọc theo ngưỡng (chưa có ngưỡng có căn cứ).

DB lưu thời gian dạng chuỗi ISO UTC (`+00:00`) → mọi mốc so sánh trong SQL phải đổi sang UTC trước.
"""

from __future__ import annotations

import argparse
import bisect
import sqlite3
import statistics
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "threads.db"
PARIS = ZoneInfo("Europe/Paris")
# Quy tắc gom lượt, không phải tham số thống kê: 1 lượt chạy ~2 phút, 2 lượt lịch cách nhau 4h
BATCH_GAP = timedelta(minutes=10)
# Khoảng trống dài hơn chu kỳ 4h + ân hạn 1h (như job_health) = ít nhất 1 lượt bị lỡ
MISSED_RUN_GAP = timedelta(hours=5)


@dataclass(frozen=True)
class Coverage:
    since: datetime
    until: datetime
    n_batches: int
    batches_per_day: float
    batches_by_paris_hour: dict[int, int]
    n_long_gaps: int  # khoảng trống > MISSED_RUN_GAP
    median_long_gap_hours: float | None
    n_posts_24h: int  # số root post đủ tuổi để đếm điểm trong 24h đầu
    points_first_24h: list[int]  # đã sắp xếp
    smallest_batches: list[tuple[datetime, int]]  # (bắt đầu, số dòng), ít dòng nhất trước


def batch_starts(fetched: Sequence[datetime]) -> list[datetime]:
    """Gom các `fetched_at` (đã sắp xếp) thành lượt; trả thời điểm bắt đầu mỗi lượt."""
    starts: list[datetime] = []
    previous: datetime | None = None
    for t in fetched:
        if previous is None or t - previous >= BATCH_GAP:
            starts.append(t)
        previous = t
    return starts


def coverage(conn: sqlite3.Connection, since: datetime, now: datetime) -> Coverage:
    since_utc = since.astimezone(UTC).isoformat()  # so chuỗi với dữ liệu UTC trong DB
    rows = [
        (post_id, datetime.fromisoformat(at))
        for post_id, at in conn.execute(
            "SELECT post_id, fetched_at FROM insights_snapshots WHERE fetched_at >= ? "
            "ORDER BY fetched_at",
            (since_utc,),
        )
    ]
    starts = batch_starts([at for _, at in rows])
    batch_of = [bisect.bisect_right(starts, at) - 1 for _, at in rows]  # chỉ số lượt của mỗi dòng
    sizes = Counter(batch_of)
    days = (now - since).total_seconds() / 86400
    gaps = [b - a for a, b in zip(starts, starts[1:], strict=False)]
    long_gaps = [g.total_seconds() / 3600 for g in gaps if g > MISSED_RUN_GAP]
    hours = Counter(s.astimezone(PARIS).hour for s in starts)

    batches_by_post: dict[str, list[tuple[datetime, int]]] = {}
    for (post_id, at), batch in zip(rows, batch_of, strict=True):
        batches_by_post.setdefault(post_id, []).append((at, batch))

    points: list[int] = []
    roots = conn.execute(
        "SELECT id, timestamp FROM posts "
        "WHERE reply_role IS NULL AND is_reply = 0 AND timestamp >= ?",
        (since_utc,),
    ).fetchall()
    for post_id, ts in roots:
        posted = datetime.fromisoformat(ts)
        if now - posted < timedelta(hours=24):
            continue
        window_end = posted + timedelta(hours=24)
        seen = {b for at, b in batches_by_post.get(post_id, []) if posted <= at < window_end}
        points.append(len(seen))

    smallest = sorted((sizes[i], starts[i]) for i in range(len(starts)))[:3]
    return Coverage(
        since=since,
        until=now,
        n_batches=len(starts),
        batches_per_day=len(starts) / days if days > 0 else 0.0,
        batches_by_paris_hour=dict(sorted(hours.items())),
        n_long_gaps=len(long_gaps),
        median_long_gap_hours=statistics.median(long_gaps) if long_gaps else None,
        n_posts_24h=len(points),
        points_first_24h=sorted(points),
        smallest_batches=[(start, size) for size, start in smallest],
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Insight snapshot coverage (ADR-0017)")
    parser.add_argument("--since", default="2026-09-10", help="ngày bắt đầu (giờ Paris)")
    args = parser.parse_args(argv)
    since = datetime.fromisoformat(args.since).replace(tzinfo=PARIS)
    now = datetime.now(PARIS)
    # Chỉ đọc: không tạo DB rỗng trong worktree thiếu `data/threads.db`
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        c = coverage(conn, since, now)
    finally:
        conn.close()
    gap = f"{c.median_long_gap_hours:.1f}h" if c.median_long_gap_hours is not None else "n/a"
    median_points = f"{statistics.median(c.points_first_24h):g}" if c.points_first_24h else "n/a"
    print(f"since {c.since:%Y-%m-%d} to {c.until:%Y-%m-%d %H:%M} Paris")
    print(f"batches: n={c.n_batches} ({c.batches_per_day:.1f}/day)")
    print(f"batches by Paris hour: {c.batches_by_paris_hour}")
    print(f"gaps > {MISSED_RUN_GAP.total_seconds() / 3600:.0f}h: n={c.n_long_gaps}, median {gap}")
    print(
        f"snapshots in first 24h per root post: n={c.n_posts_24h} posts, "
        f"median {median_points}, values {c.points_first_24h}"
    )
    smallest = ", ".join(
        f"{start.astimezone(PARIS):%Y-%m-%d %H:%M} ({size} rows)"
        for start, size in c.smallest_batches
    )
    print(f"smallest batches (Paris): {smallest or 'n/a'}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.exit(main())
