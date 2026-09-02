from __future__ import annotations

from src.models.insight_snapshot import InsightSnapshot


def view_velocity(t1: InsightSnapshot, t2: InsightSnapshot) -> float:
    """(views_t2 - views_t1) / (t2 - t1, giờ) — xem docs/claude/data-model.md
    "Metric Architecture" mục "Velocity & Momentum".

    `t1`/`t2` phải cùng `post_id`, `t2.fetched_at` phải sau `t1.fetched_at` — hàm
    KHÔNG tự sắp xếp lại thứ tự, gọi sai thứ tự sẽ trả về giá trị âm."""
    delta_hours = (t2.fetched_at - t1.fetched_at).total_seconds() / 3600
    if delta_hours <= 0:
        raise ValueError("t2.fetched_at phải sau t1.fetched_at")
    return (t2.views - t1.views) / delta_hours


def amplification_velocity(t1: InsightSnapshot, t2: InsightSnapshot) -> float:
    """Δ(reposts + quotes) / Δt (giờ) — tốc độ redistribute, khác `view_velocity`
    (tốc độ tiếp cận). 2 tín hiệu độc lập: 1 post có thể tăng view nhanh (thuật
    toán đẩy) mà không ai repost/quote (không lan truyền chủ động)."""
    delta_hours = (t2.fetched_at - t1.fetched_at).total_seconds() / 3600
    if delta_hours <= 0:
        raise ValueError("t2.fetched_at phải sau t1.fetched_at")
    delta_amplification = (t2.reposts + t2.quotes) - (t1.reposts + t1.quotes)
    return delta_amplification / delta_hours
