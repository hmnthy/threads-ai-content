"""Entry point cho job chạy định kỳ (Windows Task Scheduler, mỗi 4h) — bắt post mới
(nếu có) + lấy snapshot insights fresh cho toàn bộ content unit. Bắt buộc
`use_cache=False`: tần suất 4h < TTL cache 6h (xem `run_ingest` docstring), dùng cache
sẽ có nguy cơ bỏ lỡ post đăng giữa 2 lần chạy.

Task Scheduler gọi (không console, ADR-0013):
`.venv\\Scripts\\pythonw.exe -m src.pipeline.scheduled_job --log data\\logs\\scheduled_job.log`
Chạy tay (in ra màn hình): `uv run python -m src.pipeline.scheduled_job`

Chỉ import thư viện chuẩn + `job_log` ở đầu file: module dự án import trong `_snapshot`
để lỗi import (VD đang `uv sync` dở) cũng có traceback trong log.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from src.pipeline.job_log import run_job


def _snapshot() -> object:
    from src.pipeline.ingest import run_ingest

    return asyncio.run(run_ingest(use_cache=False))


REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = REPO_ROOT / "data" / "logs" / "scheduled_job.log"  # log chuẩn (cron + job_health)


def main(argv: Sequence[str] | None = None, status_log: Path | None = LOG_PATH) -> int:
    return run_job("scheduled_job", "Snapshot job (4h)", _snapshot, argv, status_log)


if __name__ == "__main__":
    sys.exit(main())
