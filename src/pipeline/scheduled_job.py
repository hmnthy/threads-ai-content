"""Entry point cho job chạy định kỳ (Windows Task Scheduler, mỗi 4h) — bắt post mới
(nếu có) + lấy snapshot insights fresh cho toàn bộ content unit. Bắt buộc
`use_cache=False`: tần suất 4h < TTL cache 6h (xem `run_ingest` docstring), dùng cache
sẽ có nguy cơ bỏ lỡ post đăng giữa 2 lần chạy.

Chạy tay: `.venv/Scripts/python.exe -m src.pipeline.scheduled_job`
Log ra stdout, Task Scheduler tự redirect vào file log (xem lệnh setup trong
architecture.md quyết định 2026-09-01 hoặc hỏi lại nếu chưa ghi).
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from src.pipeline.ingest import run_ingest


async def _main() -> None:
    started = datetime.now(UTC)
    try:
        result = await run_ingest(use_cache=False)
    except Exception as exc:  # noqa: BLE001 — job chạy không giám sát, log lỗi thay vì crash im lặng
        print(f"[{started.isoformat()}] scheduled_job LỖI: {exc!r}", file=sys.stderr)
        raise
    finished = datetime.now(UTC)
    print(f"[{started.isoformat()} -> {finished.isoformat()}] scheduled_job xong: {result}")


if __name__ == "__main__":
    asyncio.run(_main())
