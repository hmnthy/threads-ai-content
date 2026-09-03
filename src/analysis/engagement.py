from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from zoneinfo import ZoneInfo

from src.api.models import PostInsights, ThreadsPost

# Ngưỡng mẫu tối thiểu/bucket để được phép tuyên bố 1 kết luận về bucket đó (VD
# "giờ này engagement cao hơn") — mượn từ `vunderkind/threads-analytics` (xem
# docs/claude/data-model.md "Narrative Layering Principle"). Bucket có ít bài hơn
# ngưỡng này được đánh dấu `insufficient_data=True`, KHÔNG bị loại khỏi kết quả
# (vẫn trả về số liệu thô, chỉ là không đủ căn cứ để diễn giải bằng lời — tầng 6).
MIN_N_PER_BUCKET: Final[int] = 5


def _insights_by_post_id(insights: list[PostInsights]) -> dict[str, PostInsights]:
    return {item.post_id: item for item in insights}


def average_engagement_rate(insights: list[PostInsights]) -> float:
    """Mean of PostInsights.engagement_rate across all given posts; 0.0 if empty."""
    if not insights:
        return 0.0
    return sum(item.engagement_rate for item in insights) / len(insights)


def median_engagement_rate(insights: list[PostInsights]) -> float:
    """Median of PostInsights.engagement_rate — dùng song song `average_engagement_rate()`
    (mean) khi cần central tendency bền với outlier (tầng 3 "Narrative Layering
    Principle", xem docs/claude/data-model.md). Mean bị kéo lệch mạnh bởi 1 bài
    viral duy nhất trong tập; median phản ánh "trải nghiệm điển hình" tốt hơn — case
    thực nghiệm median 412 vs mean 2.254 (gấp 5.5 lần, nguồn `Hwemo-Chung/threads-
    analytics`) là lý do kỹ thuật cho hàm này. Không thay thế `average_engagement_rate`
    — 2 con số nên đi cùng nhau, chênh lệch lớn giữa chúng TỰ NÓ là 1 câu chuyện
    thống kê đáng nêu (không phải nhiễu cần bỏ qua)."""
    if not insights:
        return 0.0
    return statistics.median(item.engagement_rate for item in insights)


def top_posts_by_engagement(
    posts: list[ThreadsPost], insights: list[PostInsights], limit: int = 10
) -> list[tuple[ThreadsPost, PostInsights]]:
    """Posts paired with their insights, sorted by engagement rate descending.

    Posts with no matching insights (by id) are skipped.
    """
    by_id = _insights_by_post_id(insights)
    paired = [(post, by_id[post.id]) for post in posts if post.id in by_id]
    return sorted(paired, key=lambda pair: pair[1].engagement_rate, reverse=True)[:limit]


@dataclass(frozen=True)
class EngagementBucketStats:
    """Thống kê engagement_rate của 1 bucket (giờ/thứ) — tầng 3 "Narrative Layering
    Principle" (central tendency + spread), xem docs/claude/data-model.md.

    Giữ song song `mean` và `median` CỐ TÌNH — chênh lệch giữa 2 giá trị tự nó là
    1 câu chuyện thống kê thật, không phải nhiễu (case thực nghiệm median 412 vs
    mean 2.254, gấp 5.5 lần, nguồn `Hwemo-Chung/threads-analytics`: "giờ tốt nhất
    theo mean lại là giờ tệ nhất theo median" — do 1 bài viral kéo lệch mean của
    đúng bucket đó). Tầng trình bày (dashboard/report) nên hiện cả 2 cạnh nhau,
    không chỉ chọn 1.

    `iqr_low`/`iqr_high` = Q1/Q3 (percentile 25/75, `statistics.quantiles(...,
    method="inclusive")` — ổn định hơn cho mẫu nhỏ so với "exclusive" mặc định).
    Với `n < 2`, không đủ điểm để tính IQR có ý nghĩa — trả về `iqr_low=iqr_high=median`
    (spread bằng 0, đúng bản chất "chỉ có 1 điểm quan sát").

    `insufficient_data=True` khi `n < MIN_N_PER_BUCKET` — tránh tuyên bố "giờ này
    tốt nhất" chỉ từ 1-2 bài.
    """

    median: float
    mean: float
    n: int
    iqr_low: float
    iqr_high: float
    insufficient_data: bool


def engagement_by_hour(
    posts: list[ThreadsPost], insights: list[PostInsights], *, timezone: ZoneInfo | None = None
) -> dict[int, EngagementBucketStats]:
    """Engagement rate bucketed by post hour (0-23) — median/mean/n/IQR/insufficient_data
    per bucket, xem `EngagementBucketStats`.

    Threads timestamps are UTC. Pass `timezone` (e.g. ZoneInfo("Europe/Paris") or
    ZoneInfo("Asia/Ho_Chi_Minh")) to bucket by that zone's local hour instead —
    call this once per audience timezone to compare them, since Threads doesn't
    expose which timezone/country any given engagement actually came from.
    """
    return _bucket_stats(posts, insights, key=lambda post: _localize(post.timestamp, timezone).hour)


def engagement_by_weekday(
    posts: list[ThreadsPost], insights: list[PostInsights], *, timezone: ZoneInfo | None = None
) -> dict[int, EngagementBucketStats]:
    """Engagement rate bucketed by weekday (0=Monday .. 6=Sunday) — median/mean/n/IQR/
    insufficient_data per bucket, xem `EngagementBucketStats`.

    Threads timestamps are UTC. Pass `timezone` to bucket by that zone's local
    weekday instead — matters near local midnight, where a post can fall on a
    different calendar day once converted (see engagement_by_hour)."""
    return _bucket_stats(
        posts, insights, key=lambda post: _localize(post.timestamp, timezone).weekday()
    )


def _localize(timestamp: datetime, timezone: ZoneInfo | None) -> datetime:
    return timestamp if timezone is None else timestamp.astimezone(timezone)


def _bucket_stats(
    posts: list[ThreadsPost],
    insights: list[PostInsights],
    *,
    key: Callable[[ThreadsPost], int],
) -> dict[int, EngagementBucketStats]:
    by_id = _insights_by_post_id(insights)
    buckets: dict[int, list[float]] = defaultdict(list)
    for post in posts:
        item = by_id.get(post.id)
        if item is not None:
            buckets[key(post)].append(item.engagement_rate)
    return {bucket: _stats_for(rates) for bucket, rates in buckets.items()}


def _stats_for(rates: list[float]) -> EngagementBucketStats:
    n = len(rates)
    median = statistics.median(rates)
    mean = sum(rates) / n
    if n >= 2:
        q1, _, q3 = statistics.quantiles(rates, n=4, method="inclusive")
    else:
        q1 = q3 = median
    return EngagementBucketStats(
        median=median,
        mean=mean,
        n=n,
        iqr_low=q1,
        iqr_high=q3,
        insufficient_data=n < MIN_N_PER_BUCKET,
    )
