"""Distribution stats dùng chung — extract từ `engagement.py` (Layer 2 cũ) để tái
dùng cho Share rate/Conversation trong KPI strip cửa sổ thời gian (Overview mới),
tránh viết lặp lại median+mean+n+IQR+insufficient_data 3 lần cho 3 index khác nhau.
Đúng pattern "engine dùng chung" đã áp dụng cho `significance.compare_groups()`.

QUAN TRỌNG: mockup UI (`overview-amber.dc.html`) tự tính hero/KPI bằng pooled ratio
(Σinteractions/Σviews) — đó là code demo cho ĐẸP, KHÔNG phải methodology. Methodology
thật của dự án (đã chốt ở Layer 2, xem docs/claude/data-model.md "Narrative Layering
Principle") là phân phối CỦA TỪNG POST (median, IQR, n — mean chỉ để phân tích, UI không
hiện, ADR-0023), không phải tỉ lệ gộp. Module này giữ đúng
methodology gốc — mockup không được phép ảnh hưởng tới đây."""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass

# Mượn lại đúng ngưỡng đã chốt ở engagement.py (Layer 2) — 1 nguồn duy nhất, xem
# đó cho lý do đầy đủ. Import trực tiếp thay vì định nghĩa lại để tránh 2 hằng số
# có thể lệch nhau qua thời gian.
from src.analysis.engagement import MIN_N_PER_BUCKET as MIN_N_PER_BUCKET
from src.api.models import PostInsights, ThreadsPost

__all__ = [
    "DistributionStats",
    "MIN_N_PER_BUCKET",
    "distribution_stats",
    "split_measurable",
    "views_floor",
    "window_stats",
]


@dataclass(frozen=True)
class DistributionStats:
    """Median/mean/n/IQR/insufficient_data của 1 tập giá trị liên tục — dùng cho cả
    bucket giờ/thứ (engagement.py) LẪN aggregate theo cửa sổ thời gian (share rate/
    conversation/engagement). Giữ mean+median song song CỐ TÌNH (mean cho phân tích, UI
    không hiện — ADR-0023) — xem docstring gốc
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


def split_measurable(
    posts: list[ThreadsPost], insights: list[PostInsights]
) -> tuple[list[ThreadsPost], list[PostInsights], int]:
    """Tách các bài ĐO ĐƯỢC rate (snapshot mới nhất có `views > 0`) khỏi các bài
    `views == 0` — ADR-0011: views = 0 là insight thiếu, không phải 0% tương tác.
    `PostInsights.engagement_rate` trả 0.0 khi views = 0 (guard chia 0), nếu để lọt
    vào phân phối thì thành số 0 giả kéo lệch median/n.

    Trả `(posts_giữ, insights_giữ, số_bài_bị_loại)` — người gọi PHẢI báo số bị loại
    ra ngoài (`excluded_no_views`), không được loại ngầm. Bài không có insight nào
    không được tính vào số bị loại (chúng vốn đã không nằm trong phân tích)."""
    measurable = [item for item in insights if item.views > 0]
    kept_ids = {item.post_id for item in measurable}
    kept_posts = [post for post in posts if post.id in kept_ids]
    return kept_posts, measurable, len(insights) - len(measurable)


def views_floor(insights: list[PostInsights]) -> float | None:
    """Sàn views cho bảng top theo tỉ lệ (ADR-0023 1f): P25 views của các bài đo được, tính lại từ
    dữ liệu mỗi lần (quy tắc, không phải hằng số). Cùng cách tính phân vị với IQR của
    `distribution_stats` — `statistics.quantiles(method="inclusive")`, nội suy tuyến tính (Hyndman
    & Fan 1996 loại 7). Căn cứ: tỉ lệ của bài ít views dao động ~5 lần nhiều hơn (sai số chuẩn nhị
    thức, ADR-0023 mục 7). `insights` đã qua `split_measurable`; < 2 bài → None (không có phân vị,
    người gọi không lọc)."""
    if len(insights) < 2:
        return None
    q1, _, _ = statistics.quantiles([item.views for item in insights], n=4, method="inclusive")
    return q1


def window_stats(
    insights: list[PostInsights], metric: Callable[[PostInsights], float]
) -> DistributionStats:
    """`distribution_stats()` áp `metric` lên từng `PostInsights` trong 1 cửa sổ —
    dùng chung cho engagement/share rate/conversation của KPI strip cửa sổ thời gian:
    `window_stats(insights, lambda i: i.engagement_rate)`,
    `window_stats(insights, share_rate)`, `window_stats(insights, conversation_rate)`.
    """
    return distribution_stats([metric(item) for item in insights])
