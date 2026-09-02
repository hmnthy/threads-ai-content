"""Snapshot job (Bước 5, CHỈ phần thu thập) — fetch insights hiện tại cho toàn bộ
post, insert vào `insights_snapshots`. Mỗi lần chạy APPEND 1 snapshot mới cho mỗi
post, KHÔNG ghi đè — `velocity.py`/`longevity.py` (Bước 5 phần tính toán + Bước 6,
CHƯA VIẾT tối nay) cần nhiều điểm snapshot tích luỹ theo thời gian mới tính được.

Script đã sẵn sàng để chạy định kỳ (cron / Task Scheduler) — **tần suất bao nhiêu
là quyết định cần chủ dự án xác nhận, KHÔNG tự setup lịch chạy ở đây** (xem CLAUDE.md
task scope). Chạy tay 1 lần: `.venv/Scripts/python.exe -m src.pipeline.snapshot`.
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime

from src.api.client import ThreadsClient
from src.api.endpoints import get_post_insights
from src.db.schema import insert_insight_snapshot
from src.models.insight_snapshot import InsightSnapshot


async def fetch_and_store_insights_snapshot(
    client: ThreadsClient, conn: sqlite3.Connection, post_ids: list[str]
) -> int:
    """Gọi `get_post_insights()` tuần tự cho từng post_id, insert 1 InsightSnapshot
    mỗi post (fetched_at = now). Tuần tự (không concurrent) — rate limit Threads rất
    cao (4,800 x impressions/24h) nên không bắt buộc, nhưng an toàn hơn cho 1 job
    chạy nền không giám sát. Trả về số snapshot đã insert."""
    count = 0
    for post_id in post_ids:
        insights = await get_post_insights(client, post_id)
        snapshot = InsightSnapshot(
            post_id=post_id,
            fetched_at=datetime.now(UTC),
            views=insights.views,
            likes=insights.likes,
            replies=insights.replies,
            reposts=insights.reposts,
            quotes=insights.quotes,
        )
        insert_insight_snapshot(conn, snapshot)
        count += 1
    conn.commit()
    return count


async def _main() -> None:
    from src.api.auth import load_credentials
    from src.db.schema import DEFAULT_DB_PATH, connect, list_content_units

    creds = load_credentials()
    conn = connect(DEFAULT_DB_PATH)
    post_ids = [row["id"] for row in list_content_units(conn)]
    async with ThreadsClient(access_token=creds.access_token) as client:
        count = await fetch_and_store_insights_snapshot(client, conn, post_ids)
    conn.close()
    print(f"Inserted {count} insight snapshots for {len(post_ids)} content units.")


if __name__ == "__main__":
    asyncio.run(_main())
