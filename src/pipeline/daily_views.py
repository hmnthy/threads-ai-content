"""Ingest account-level daily views — khác `snapshot.py` (per-post
lifetime snapshot): đây là 1 điểm/ngày cho TOÀN kênh, từ `threads_insights?metric=
views&period=day`, verify live 2026-09-03 (xem `src/api/endpoints.py`
`get_account_daily_views`, cap lookback 729 ngày).

Lần đầu chạy (bảng `account_daily_views` rỗng): backfill full 729 ngày. Các lần
sau: chỉ refetch DAILY_VIEWS_REFRESH_WINDOW_DAYS ngày gần nhất — đủ để bắt số liệu
Meta backfill trễ (vài ngày đầu thường thấp hơn số cuối cùng), không cần fetch lại
toàn bộ lịch sử mỗi lần. Gộp vào job Task Scheduler `ThreadsAI_SnapshotJob_4h` có sẵn
(hàm này idempotent qua UPSERT, chạy nhiều lần/ngày không sao). Nhãn ngày = ngày Pacific mà
điểm đo (ADR-0034); sau lần dời nhãn dữ liệu cũ, lần chạy đầu tải lại đủ 729 ngày một lần.

Chạy tay: `.venv/Scripts/python.exe -m src.pipeline.daily_views`.
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta

from src.api.client import ThreadsClient
from src.api.endpoints import DAILY_VIEWS_LOOKBACK_CAP_DAYS, get_account_daily_views
from src.db.schema import (
    DAILY_VIEWS_REFETCH_MIGRATION,
    DAILY_VIEWS_RELABEL_MIGRATION,
    list_daily_views,
    mark_migration_applied,
    migration_applied,
    upsert_daily_views,
)

DAILY_VIEWS_REFRESH_WINDOW_DAYS = 7


async def fetch_and_store_daily_views(
    client: ThreadsClient, conn: sqlite3.Connection, user_id: str
) -> int:
    """Backfill toàn bộ lịch sử nếu bảng rỗng hoặc chưa tải lại sau khi dời nhãn ngày (ADR-0034),
    ngược lại chỉ refetch vài ngày gần nhất. Trả về số điểm đã upsert.

    Bảng còn nhãn theo quy ước cũ (chưa qua `create_schema()` của bản này) → dừng: ghi nhãn mới
    vào đó rồi migration dời +1 ngày lần nữa là sai cả chuỗi."""
    if not migration_applied(conn, DAILY_VIEWS_RELABEL_MIGRATION):
        raise RuntimeError(
            "account_daily_views still uses the old day labels — run create_schema() first "
            "(ADR-0034)"
        )
    today = datetime.now(UTC).date()
    existing = list_daily_views(conn)
    full = not existing or not migration_applied(conn, DAILY_VIEWS_REFETCH_MIGRATION)
    if full:
        since = today - timedelta(days=DAILY_VIEWS_LOOKBACK_CAP_DAYS)
    else:
        since = today - timedelta(days=DAILY_VIEWS_REFRESH_WINDOW_DAYS)

    # Gọi mạng xong mới ghi — không giữ transaction ghi qua lời gọi API
    points = await get_account_daily_views(client, user_id, since, today)
    fetched_at = datetime.now(UTC).isoformat()
    for point in points:
        upsert_daily_views(conn, date=point.date, views=point.views, fetched_at=fetched_at)
    if full and points:  # Meta trả rỗng → chưa tải lại được gì, lần sau thử lại
        mark_migration_applied(conn, DAILY_VIEWS_REFETCH_MIGRATION)
    conn.commit()
    return len(points)


async def _main() -> None:
    from src.api.auth import load_credentials
    from src.db.schema import DEFAULT_DB_PATH, connect, create_schema

    creds = load_credentials()
    conn = connect(DEFAULT_DB_PATH)
    try:
        create_schema(conn)
        async with ThreadsClient(access_token=creds.access_token) as client:
            count = await fetch_and_store_daily_views(client, conn, creds.user_id)
    finally:
        conn.close()
    print(f"Upserted {count} daily view points.")


if __name__ == "__main__":
    asyncio.run(_main())
