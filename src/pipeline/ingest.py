"""Batch pipeline: fetch posts+replies từ Threads API → build ContentUnit →
normalize text → lưu SQLite → seed insights_snapshots ban đầu.

Tách khỏi FastAPI serving layer — `src/main.py` chỉ đọc kết quả đã tính sẵn từ
SQLite, KHÔNG tự gọi API/build lại content unit mỗi request (xem
docs/claude/architecture.md quyết định "Batch pipeline tách riêng khỏi FastAPI
serving layer"). Chạy tay: `.venv/Scripts/python.exe -m src.pipeline.ingest`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from src.api.auth import load_credentials
from src.api.cache import Cache
from src.api.client import ThreadsClient
from src.api.endpoints import get_posts, get_replies
from src.db.schema import (
    DEFAULT_DB_PATH,
    connect,
    create_schema,
    update_content_unit_text,
    upsert_content_unit,
    upsert_post,
)
from src.pipeline.snapshot import fetch_and_store_insights_snapshot
from src.processing.text import normalize_text
from src.processing.thread_reconstruction import build_content_units


async def run_ingest(db_path: Path = DEFAULT_DB_PATH, *, use_cache: bool = True) -> dict[str, int]:
    """Ingest toàn bộ posts + replies hiện có của kênh, build ContentUnit, lưu SQLite,
    và fetch snapshot insights đầu tiên cho mỗi content unit. Idempotent trên
    posts/content_units (upsert theo id) — chạy lại an toàn, KHÔNG idempotent trên
    insights_snapshots (mỗi lần chạy append 1 snapshot mới, đúng ý đồ thiết kế).

    `use_cache=False` bắt buộc cho job chạy định kỳ (cron/Task Scheduler) tần suất
    <6h (TTL cache mặc định) — nếu không, `get_posts`/`get_replies` có thể trả cache
    cũ hơn khoảng cách giữa 2 lần chạy, bỏ lỡ post mới đăng trong lúc đó. `get_post_
    insights()` (dùng cho snapshot) KHÔNG qua cache dù `use_cache` là gì — luôn fresh."""
    creds = load_credentials()
    cache = Cache() if use_cache else None
    conn = connect(db_path)
    create_schema(conn)

    async with ThreadsClient(access_token=creds.access_token) as client:
        posts = await get_posts(client, creds.user_id, cache=cache)
        replies = await get_replies(client, creds.user_id, cache=cache)
        units = build_content_units(posts, replies)

        for post in [*posts, *replies]:
            upsert_post(conn, post)
        for unit in units:
            upsert_content_unit(conn, unit)
            update_content_unit_text(
                conn,
                unit.id,
                raw_text=unit.full_text,
                normalized_text=normalize_text(unit.full_text),
            )
        conn.commit()

        snapshot_count = await fetch_and_store_insights_snapshot(
            client, conn, [unit.id for unit in units]
        )

    conn.close()
    return {
        "posts": len(posts),
        "replies": len(replies),
        "content_units": len(units),
        "multi_post_units": sum(1 for unit in units if unit.is_multi_post),
        "insight_snapshots": snapshot_count,
    }


if __name__ == "__main__":
    result = asyncio.run(run_ingest())
    print(result)
