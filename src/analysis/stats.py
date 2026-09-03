"""Distribution stats dùng chung — extract từ `engagement.py` (Layer 2 cũ) để tái
dùng cho Virality/Conversation trong KPI strip cửa sổ thời gian (Overview mới),
tránh viết lặp lại median+mean+n+IQR+insufficient_data 3 lần cho 3 index khác nhau.
Đúng pattern "engine dùng chung" đã áp dụng cho `significance.compare_groups()`.

QUAN TRỌNG: mockup UI (`overview-amber.dc.html`) tự tính hero/KPI bằng pooled ratio
(Σinteractions/Σviews) — đó là code demo cho ĐẸP, KHÔNG phải methodology. Methodology
thật của dự án (đã chốt ở Layer 2, xem docs/claude/data-model.md "Narrative Layering
Principle") là median+mean CỦA TỪNG POST, không phải tỉ lệ gộp. Module này giữ đúng
methodology gốc — mockup không được phép ảnh hưởng tới đây."""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass

# Mượn lại đúng ngưỡng đã chốt ở engagement.py (Layer 2) — 1 nguồn duy nhất, xem
# đó cho lý do đầy đủ. Import trực tiếp thay vì định nghĩa lại để tránh 2 hằng số
# có thể lệch nhau qua thời gian.
from src.analysis.engagement import MIN_N_PER_BUCKET as MIN_N_PER_BUCKET
from src.api.models import PostInsights

__all__ = ["DistributionStats", "MIN_N_PER_BUCKET", "distribution_stats", "window_stats"]


@dataclass(frozen=True)
class DistributionStats:
    """Median/mean/n/IQR/insufficient_data của 1 tập giá trị liên tục — dùng cho cả
    bucket giờ/thứ (engagement.py) LẪN aggregate theo cửa sổ thời gian (virality/
    conversation/engagement). Giữ mean+median song song CỐ TÌNH — xem docstring gốc
    `EngagementBucketStats` (engagement.py) cho lý do đầy đủ (case Hwemo-Chung)."""

    median: float
    mean: float
    n: int
    iqr_low: float
    iqr_high: float
    insufficient_data: bool


def distribution_stats(values: list[float]) -> DistributionStats:
    """Hàm thuần — không biết gì về post/insight, chỉ nhận list số. `n=0` trả về
    toàn 0.0, `insufficient_data=True` (không có gì để tuyên bố)."""
    n = len(values)
    if n == 0:
        return DistributionStats(
            median=0.0, mean=0.0, n=0, iqr_low=0.0, iqr_high=0.0, insufficient_data=True
        )
    median = statistics.median(values)
    mean = sum(values) / n
    if n >= 2:
        q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    else:
        q1 = q3 = median
    return DistributionStats(
        median=median,
        mean=mean,
        n=n,
        iqr_low=q1,
        iqr_high=q3,
        insufficient_data=n < MIN_N_PER_BUCKET,
    )


def window_stats(
    insights: list[PostInsights], metric: Callable[[PostInsights], float]
) -> DistributionStats:
    """`distribution_stats()` áp `metric` lên từng `PostInsights` trong 1 cửa sổ —
    dùng chung cho engagement/virality/conversation của KPI strip cửa sổ thời gian:
    `window_stats(insights, lambda i: i.engagement_rate)`,
    `window_stats(insights, virality_index)`, `window_stats(insights, conversation_rate)`.
    """
    return distribution_stats([metric(item) for item in insights])
