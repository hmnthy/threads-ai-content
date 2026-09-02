"""InsightSnapshot — 1 lần đo `PostInsights` tại 1 thời điểm cụ thể (`fetched_at`).

Threads API chỉ trả tổng số liệu lifetime tại thời điểm gọi, không có history — để
tính `velocity`/`longevity` (xem docs/claude/data-model.md "Metric Architecture") cần
tự tích luỹ nhiều snapshot theo thời gian bằng cách gọi lại `get_post_insights()` định
kỳ và lưu mỗi lần gọi thành 1 row `InsightSnapshot` (bảng `insights_snapshots`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class InsightSnapshot:
    post_id: str
    fetched_at: datetime
    views: int
    likes: int
    replies: int
    reposts: int
    quotes: int
