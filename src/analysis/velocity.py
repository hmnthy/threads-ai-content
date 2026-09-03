from __future__ import annotations

import numpy as np

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


def window_velocity(snapshots: list[InsightSnapshot]) -> float:
    """Hệ số góc hồi quy tuyến tính `views ~ time` (views/giờ) trên TOÀN BỘ chuỗi
    snapshot trong 1 window — KHÁC `view_velocity` (chỉ 2 điểm đầu-cuối).

    Yêu cầu `len(snapshots) >= 3` — dưới 3 điểm không đủ để hồi quy có ý nghĩa hơn
    đường thẳng nối 2 điểm (dùng `view_velocity` cho trường hợp đó); raise
    `ValueError` nếu vi phạm.

    **Vì sao cần hàm này bên cạnh `view_velocity`** (xem docs/claude/data-model.md
    "Metric Architecture" mục "Velocity & Momentum"): `view_velocity` chỉ nhìn 2
    điểm đầu-cuối, nhạy với nhiễu do lịch cron snapshot không hoàn hảo (VD 1 lần
    gọi API bị trễ/lỗi khiến khoảng cách giữa 2 điểm đầu-cuối không đại diện đúng
    tốc độ trung bình cả window). Hồi quy trên TOÀN BỘ điểm quan sát được (VD ~6
    điểm/24h với cron 4h) ổn định hơn trước nhiễu đó.

    Không tự sắp xếp `snapshots` theo `fetched_at` trước khi trả về — nhưng KHÔNG
    yêu cầu input đã sắp xếp sẵn (mốc thời gian tương đối tự tính từ `min(fetched_at)`
    trong chính tập truyền vào, hồi quy tuyến tính không phụ thuộc thứ tự input).
    Giống `view_velocity`, hàm giả định mọi snapshot cùng `post_id` — không tự
    kiểm tra, người gọi chịu trách nhiệm lọc trước.

    Ở tầng trình bày (dashboard/report), LUÔN hiện chuỗi snapshot thô (timestamp,
    views tại từng điểm — tầng 1 "Narrative Layering Principle") TRƯỚC khi hiện
    slope tính ra (tầng 2/3, con số phái sinh) — không đem 1 con số velocity ra
    mà không ai thấy nó từ đâu ra.
    """
    if len(snapshots) < 3:
        raise ValueError("window_velocity cần >= 3 snapshot (2 điểm dùng view_velocity)")
    t0 = min(snapshot.fetched_at for snapshot in snapshots)
    hours = np.array([(s.fetched_at - t0).total_seconds() / 3600 for s in snapshots])
    views = np.array([float(s.views) for s in snapshots])
    slope, _intercept = np.polyfit(hours, views, 1)
    return float(slope)
