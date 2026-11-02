"""Hai quy ước "ngày" của sản phẩm (ADR-0034) — mọi chỗ đổi thời điểm → ngày đi qua module này.

1. Chuỗi views theo ngày của tài khoản (`account_daily_views`): ranh giới ngày do Meta đặt — nửa
   đêm giờ Pacific (`America/Los_Angeles`, có giờ mùa hè). Meta chỉ trả TỔNG mỗi ngày, nên không
   cắt lại được theo múi giờ khác. `end_time` của mỗi điểm là nửa đêm ĐẦU ngày mà giá trị đo
   (verify live 2026-11-01: 730 điểm, `07:00Z` khi Pacific ở giờ mùa hè, `08:00Z` khi ở giờ mùa
   đông; bài đầu tiên của kênh đăng 2025-04-14 giờ Pacific và 339 views đầu tiên nằm ở điểm
   `2025-04-14T07:00:00+0000`; 11/14 bài đăng riêng lẻ có ngày views tăng mạnh nhất trùng ngày đăng
   theo quy ước này, so với 1/14 khi coi `end_time` là cuối ngày — ADR-0034).
2. Ngày đăng bài: ngày theo giờ Paris (`Europe/Paris`), nơi tác giả sống — khớp ngày in trên thẻ
   bài của dashboard (Thy chọn 2026-11-01). Lệch với ngày Meta ở bài đăng 0h–9h sáng giờ Paris
   (bài đó vào ngày Paris D, views của nó vào ngày Pacific D-1) — giới hạn đã ghi ở ADR-0034.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Final
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

META_DAY_TZ: Final = ZoneInfo("America/Los_Angeles")
AUTHOR_TZ: Final = ZoneInfo("Europe/Paris")

_END_TIME_FORMAT: Final = "%Y-%m-%dT%H:%M:%S%z"  # "2026-10-31T07:00:00+0000"


def meta_day_of_end_time(end_time: str) -> date:
    """Ngày (lịch Pacific) mà 1 điểm `period=day` đo — ngày Pacific của chính `end_time`.

    Không gõ cứng giờ "07"/"08": cơ sở dữ liệu múi giờ (tzdata) lo cả giờ mùa hè lẫn mùa đông."""
    return _pacific(end_time).date()


def warn_if_not_pacific_midnight(end_times: list[str]) -> None:
    """1 cảnh báo cho cả lần gọi khi có `end_time` không rơi đúng nửa đêm Pacific = Meta đổi quy
    ước → vẫn gắn theo ngày Pacific (job cron không dừng), người đọc log verify live lại. Gộp 1
    dòng: lần tải lại 729 ngày không làm ngập log."""
    odd = [end_time for end_time in end_times if _pacific(end_time).time() != time(0)]
    if odd:
        logger.warning(
            "daily views: %d of %d end_time values are not Pacific midnight (first: %s) — "
            "Meta's day boundary may have changed; re-verify ADR-0034",
            len(odd),
            len(end_times),
            odd[0],
        )


def _pacific(end_time: str) -> datetime:
    return datetime.strptime(end_time, _END_TIME_FORMAT).astimezone(META_DAY_TZ)


def author_day(timestamp: str) -> str:
    """Ngày đăng (YYYY-MM-DD) theo giờ Paris của 1 timestamp ISO có múi giờ (`posts.timestamp`)."""
    return datetime.fromisoformat(timestamp).astimezone(AUTHOR_TZ).date().isoformat()


def is_meta_summer_time(day: date) -> bool:
    """Nửa đêm đầu ngày `day` (giờ Pacific) có đang ở giờ mùa hè không — dùng để dời nhãn dữ liệu
    đã lưu theo quy ước cũ (`src/db/schema.py` migration ADR-0034)."""
    return bool(datetime.combine(day, time(0), tzinfo=META_DAY_TZ).dst())
