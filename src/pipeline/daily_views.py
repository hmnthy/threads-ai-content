"""Ingest account-level daily views (Bước 3, xem plan) — khác `snapshot.py` (per-post
lifetime snapshot): đây là 1 điểm/ngày cho TOÀN kênh, từ `threads_insights?metric=
views&period=day`, verify live 2026-09-03 (xem `src/api/endpoints.py`
`get_account_daily_views`, cap lookback 729 ngày).

Lần đầu chạy (bảng `account_daily_views` rỗng): backfill full 729 ngày. Các lần
sau: chỉ refetch DAILY_VIEWS_REFRESH_WINDOW_DAYS ngày gần nhất — đủ để bắt số liệu
Meta backfill trễ (vài ngày đầu thường thấp hơn số cuối cùng), không cần fetch lại
toàn bộ lịch sử mỗi lần. Gộp vào job Task Scheduler `ThreadsAI_SnapshotJob_4h` có sẵn
(hàm này idempotent qua UPSERT, chạy nhiều lần/ngày không sao).

Chạy tay: `.venv/Scripts/python.exe -m src.pipeline.daily_views`.
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta

from src.api.client import ThreadsClient
from src.api.endpoints import DAILY_VIEWS_LOOKBACK_CAP_DAYS, get_account_daily_views
from src.db.schema import list_daily_views, upsert_daily_views

DAILY_VIEWS_REFRESH_WINDOW_DAYS = 7


async def fetch_and_store_daily_views(
    client: ThreadsClient, conn: sqlite3.Connection, user_id: str
) -> int:
    """Backfill toàn bộ lịch sử nếu bảng rỗng, ngược lại chỉ refetch vài ngày gần
    nhất. Trả về số điểm đã upsert."""
    today = datetime.now(UTC).date()
    existing = list_daily_views(conn)
    if existing:
        since = today - timedelta(days=DAILY_VIEWS_REFRESH_WINDOW_DAYS)
    else:
        since = today - timedelta(days=DAILY_VIEWS_LOOKBACK_CAP_DAYS)

    points = await get_account_daily_views(client, user_id, since, today)
    fetched_at = datetime.now(UTC).isoformat()
    for point in points:
        upsert_daily_views(conn, date=point.date, views=point.views, fetched_at=fetched_at)
    conn.commit()
    return len(points)


async def _main() -> None:
    from src.api.auth import load_credentials
    from src.db.schema import DEFAULT_DB_PATH, connect

    creds = load_credentials()
    conn = connect(DEFAULT_DB_PATH)
    async with ThreadsClient(access_token=creds.access_token) as client:
        count = await fetch_and_store_daily_views(client, conn, creds.user_id)
    conn.close()
    print(f"Upserted {count} daily view points.")


if __name__ == "__main__":
    asyncio.run(_main())
