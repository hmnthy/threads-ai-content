from __future__ import annotations

import numpy as np

from src.api.models import PostInsights


def virality_index(insights: PostInsights) -> float:
    """(reposts + quotes) / views * 100 — "bao nhiêu người xem redistribute tiếp".

    CHỈ nhận `insights` — không nhận post/age/topic (đó là explanatory variables
    riêng, xem `freshness.py`/`topic_affinity.py` khi viết — tách bạch intrinsic
    performance khỏi lý do giải thích, theo docs/claude/data-model.md "Metric
    Architecture"). Metric "shares" không tồn tại trong Threads API — loại khỏi
    công thức.
    """
    if insights.views == 0:
        return 0.0
    return (insights.reposts + insights.quotes) / insights.views * 100


def channel_virality_p90(insights: list[PostInsights]) -> float:
    """Percentile 90 của `virality_index` trên TOÀN KÊNH (hoặc 1 cửa sổ thời gian
    do người gọi tự lọc trước khi truyền vào, VD 90 ngày gần nhất — hàm này không
    tự áp cửa sổ) — dùng làm `channel_p90` cho `is_viral()`.

    Đây là tầng 4 "Narrative Layering Principle" (vị trí trong phân phối kênh,
    xem docs/claude/data-model.md) — so 1 post với LỊCH SỬ CHÍNH kênh đó, không so
    với benchmark ngoài không liên quan. Tiền lệ học thuật: Elmas 2023 (arXiv
    2303.06120) + VIRALITYNET (arXiv 2605.02358) dùng đúng pattern
    "v > P90(cộng đồng)". Trả 0.0 nếu `insights` rỗng (không có phân phối để tính).
    """
    if not insights:
        return 0.0
    values = [virality_index(item) for item in insights]
    return float(np.percentile(values, 90))


def is_viral(virality_index_value: float, channel_p90: float, views: int, floor: int) -> bool:
    """virality_index_value > channel_p90 AND views >= floor.

    Nhãn PHÁI SINH THÊM — KHÔNG thay thế `virality_index` (vẫn là continuous rate
    dùng cho mọi tính toán khác, công thức không đổi). Kết hợp 2 điều kiện đúng
    tiền lệ Elmas 2023 (arXiv 2303.06120) + VIRALITYNET (arXiv 2605.02358): chỉ
    riêng percentile-trong-kênh (`virality_index_value > channel_p90`) không đủ —
    1 post có 1 view và 1 repost cũng đạt percentile cao nhưng không có ý nghĩa gì
    (mẫu quá nhỏ để redistribution rate đáng tin) — cần thêm `floor` tuyệt đối
    trên `views` để loại các post "ăn may" vì mẫu bé.

    `floor` KHÔNG hardcode trong hàm này — đây là QUYẾT ĐỊNH CỦA NGƯỜI GỌI, tự
    tính từ phân phối `views` thật của kênh (VD P25 hoặc median views trong cùng
    cửa sổ thời gian dùng để tính `channel_p90`) và truyền vào, đúng nguyên tắc
    "calibrate từ data thật" đã áp dụng cho `freshness_weight` — hàm này không tự
    ý đoán 1 con số views "hợp lý" cho mọi kênh.

    `channel_p90` nên lấy từ `channel_virality_p90()` trên CÙNG cửa sổ thời gian
    với `views`/`virality_index_value` đang xét — hàm này không tự kiểm tra tính
    nhất quán đó, người gọi chịu trách nhiệm truyền đúng.
    """
    return virality_index_value > channel_p90 and views >= floor
