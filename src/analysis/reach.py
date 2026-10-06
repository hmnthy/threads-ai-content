"""Tầng reach (ADR-0012) — bài nào chạm tới nhiều người xem hơn mức bình thường của kênh.

Thay nhãn cũ (P90 tỉ lệ chia sẻ + sàn views P25). Ba bước, mọi ngưỡng là quy tắc
tính lại từ data mỗi lần, không phải hằng số cứng:

1. **Độ chín** (`estimate_maturity`): views của bài mới còn tăng; bài chưa đủ tuổi chưa được
   xếp tầng ("still growing"). Mốc chín đo từ đường tăng views trong `insights_snapshots`.
2. **Reach tương đối** (`relative_reach`): views ÷ median views của các bài gốc đo được đăng
   ngay trước — hiệu chỉnh việc kênh lớn dần (views thô tương quan âm với tuổi bài,
   Spearman ρ = −0.39, n = 146, 2026-10-06 — ADR-0012).
3. **Tầng** (`assign_reach_tiers`): P50 / P80 của reach tương đối trên các bài đã chín và có
   mốc so sánh → "Above median reach" / "Top 20% reach". Views thô vẫn trả kèm làm tham chiếu.

Đầu vào luôn là bài gốc ĐO ĐƯỢC (`split_measurable()`, ADR-0011), xếp theo thời gian đăng tăng dần.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np

from src.analysis.engagement import MIN_N_PER_BUCKET

# Lựa chọn thiết kế (ADR-0012), không lấy từ tài liệu: mốc so sánh = 20 bài trước — đủ dài để
# median ổn định, đủ ngắn để theo kịp tăng trưởng kênh. Độ nhạy 10/30 bài ghi trong ADR-0012.
BASELINE_WINDOW: Final[int] = 20
# Cần ít nhất nửa cửa sổ bài trước mới có mốc — các bài đầu tiên của kênh không xếp tầng.
BASELINE_MIN_PRIOR: Final[int] = BASELINE_WINDOW // 2
# P50 / P80 của reach tương đối — Thy chọn 2026-10-06 (ADR-0012); "top 20%" dễ diễn giải.
ABOVE_MEDIAN_PERCENTILE: Final[float] = 50.0
TOP_20_PERCENTILE: Final[float] = 80.0
# Độ chín: bài "chín" khi đã qua thời gian mà 90% bài theo dõi được đạt 90% views mới nhất.
MATURITY_SHARE: Final[float] = 0.9
MATURITY_QUANTILE: Final[float] = 90.0
# Chỉ bài có snapshot đầu trong 24 h sau khi đăng mới cho thấy đường tăng sớm; snapshot cuối
# ≥ 14 ngày sau khi đăng thì views mới nhất được coi là gần cuối (tại 14 ngày median đã 99%,
# n = 7, ADR-0012). Hai mốc là lựa chọn thiết kế, xem lại khi có thêm đường cong.
CURVE_FIRST_SNAPSHOT_MAX_DAYS: Final[float] = 1.0
CURVE_SETTLED_MIN_DAYS: Final[float] = 14.0

ReachStatus = Literal[
    "top_20", "above_median", "below_median", "still_growing", "no_baseline", "maturity_unknown"
]
# Trạng thái đã xếp tầng — chỉ các bài này có reach tương đối mang nghĩa (bài chưa chín bị hạ thấp)
TIERED_STATUSES: Final = frozenset({"top_20", "above_median", "below_median"})

# Một đường cong = các cặp (tuổi bài tính bằng ngày lúc chụp snapshot, views) theo thời gian.
Curve = Sequence[tuple[float, int]]


@dataclass(frozen=True)
class MaturityEstimate:
    days: float | None  # None khi chưa có đường cong nào đủ điều kiện
    n_curves: int


@dataclass(frozen=True)
class ReachTiers:
    statuses: list[ReachStatus]  # cùng thứ tự với đầu vào
    baselines: list[float | None]  # median views của các bài trước (None = chưa đủ bài trước)
    ratios: list[float | None]  # views ÷ baseline
    p50_ratio: float | None
    p80_ratio: float | None
    p50_views: float | None  # views thô ở P50 / P80 của cùng nhóm bài được xếp tầng — tham chiếu
    p80_views: float | None
    n_tiered: int
    insufficient_data: bool
    maturity: MaturityEstimate


def time_to_share(curve: Curve, share: float = MATURITY_SHARE) -> float | None:
    """Tuổi (ngày) ở snapshot đầu tiên đạt `share` × views của snapshot cuối. None khi
    đường cong rỗng hoặc views cuối = 0 (không có gì để đạt)."""
    if not curve or curve[-1][1] <= 0:
        return None
    target = share * curve[-1][1]
    return next(age for age, views in curve if views >= target)


def estimate_maturity(curves: Sequence[Curve]) -> MaturityEstimate:
    """P90 của thời gian đạt 90% views mới nhất, chỉ trên đường cong có snapshot đầu sớm
    (`CURVE_FIRST_SNAPSHOT_MAX_DAYS`) và snapshot cuối muộn (`CURVE_SETTLED_MIN_DAYS`)."""
    times = [
        t
        for curve in curves
        if curve
        and curve[0][0] < CURVE_FIRST_SNAPSHOT_MAX_DAYS
        and curve[-1][0] >= CURVE_SETTLED_MIN_DAYS
        and (t := time_to_share(curve)) is not None
    ]
    if not times:
        return MaturityEstimate(days=None, n_curves=0)
    return MaturityEstimate(
        days=float(np.percentile(times, MATURITY_QUANTILE)), n_curves=len(times)
    )


def relative_reach(
    views_in_post_order: Sequence[int],
    window: int = BASELINE_WINDOW,
    min_prior: int = BASELINE_MIN_PRIOR,
) -> tuple[list[float | None], list[float | None]]:
    """(baselines, ratios): baseline = median views của tối đa `window` bài đăng ngay trước,
    ratio = views ÷ baseline. Cả hai None khi có ít hơn `min_prior` bài trước.

    Mọi views phải > 0 (bài đã qua `split_measurable()`, ADR-0011) — views = 0 làm median
    mốc có thể bằng 0 (chia 0) và là insight thiếu, không phải độ phủ thấp."""
    if any(views <= 0 for views in views_in_post_order):
        raise ValueError("relative_reach chỉ nhận bài đo được (views > 0) — qua split_measurable()")
    baselines: list[float | None] = []
    ratios: list[float | None] = []
    for i, views in enumerate(views_in_post_order):
        prior = views_in_post_order[max(0, i - window) : i]
        if len(prior) < min_prior:
            baselines.append(None)
            ratios.append(None)
            continue
        base = float(statistics.median(prior))
        baselines.append(base)
        ratios.append(views / base)
    return baselines, ratios


def _tier_cutoffs(values: Sequence[float]) -> tuple[float | None, float | None]:
    """(P50, P80) của `values`; (None, None) khi rỗng."""
    if not values:
        return None, None
    p50, p80 = np.percentile(values, [ABOVE_MEDIAN_PERCENTILE, TOP_20_PERCENTILE])
    return float(p50), float(p80)


def assign_reach_tiers(
    views_in_post_order: Sequence[int],
    ages_days: Sequence[float],
    maturity: MaturityEstimate,
    window: int = BASELINE_WINDOW,
    min_prior: int = BASELINE_MIN_PRIOR,
) -> ReachTiers:
    """Xếp tầng mọi bài; ngưỡng P50/P80 tính trên các bài đã chín VÀ có mốc so sánh.

    `ages_days` = tuổi bài TẠI SNAPSHOT cho ra `views` (không phải tuổi tới bây giờ): cron có
    thể ngắt vài ngày (ADR-0017), bài lúc đó vẫn mang views của lúc còn non.

    Thứ tự ưu tiên trạng thái: chưa có mốc (`no_baseline`) → chưa biết mốc chín
    (`maturity_unknown`) → chưa chín (`still_growing`) → tầng theo ngưỡng (biên ≥ là đạt).
    Khi nhiều reach tương đối bằng nhau, tỉ lệ thật mỗi tầng có thể lệch khỏi 20% / 50% —
    người gọi đọc số thật từ `statuses`, không suy từ tên tầng.
    """
    if len(views_in_post_order) != len(ages_days):
        raise ValueError("views_in_post_order và ages_days phải cùng độ dài")
    baselines, ratios = relative_reach(views_in_post_order, window, min_prior)
    eligible = [
        i
        for i, ratio in enumerate(ratios)
        if ratio is not None and maturity.days is not None and ages_days[i] >= maturity.days
    ]
    p50, p80 = _tier_cutoffs([r for i in eligible if (r := ratios[i]) is not None])
    p50_views, p80_views = _tier_cutoffs([float(views_in_post_order[i]) for i in eligible])
    statuses: list[ReachStatus] = []
    for i, ratio in enumerate(ratios):
        if ratio is None:
            statuses.append("no_baseline")
        elif maturity.days is None:
            statuses.append("maturity_unknown")
        elif ages_days[i] < maturity.days:
            statuses.append("still_growing")
        elif p80 is not None and ratio >= p80:
            statuses.append("top_20")
        elif p50 is not None and ratio >= p50:
            statuses.append("above_median")
        else:
            statuses.append("below_median")
    return ReachTiers(
        statuses=statuses,
        baselines=baselines,
        ratios=ratios,
        p50_ratio=p50,
        p80_ratio=p80,
        p50_views=p50_views,
        p80_views=p80_views,
        n_tiered=len(eligible),
        insufficient_data=len(eligible) < MIN_N_PER_BUCKET,
        maturity=maturity,
    )
