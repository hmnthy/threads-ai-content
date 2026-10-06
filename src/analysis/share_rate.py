"""Điều kiện đầu vào cho MỌI hàm phân phối/xếp hạng rate trong module này (ADR-0011):
`insights` đã qua `split_measurable()` (`src/analysis/stats.py`) — bài `views == 0` là
insight thiếu; để lọt vào đây thì rate 0.0 (guard chia 0) thành số 0 giả trong phân phối.

Tên `share_rate` có từ ADR-0012 (tên cũ gợi nghĩa "lan rộng"): chỉ số đo tỉ lệ người xem đăng lại /
trích dẫn, không đo độ phủ — độ phủ (bài chạm tới nhiều người hơn mức bình thường) là tầng
reach ở `src/analysis/reach.py`.
"""

from __future__ import annotations

from src.api.models import PostInsights


def share_rate(insights: PostInsights) -> float:
    """(reposts + quotes) / views * 100 — "bao nhiêu người xem đăng lại hoặc trích dẫn bài".

    CHỈ nhận `insights` — không nhận post/age/topic (đó là explanatory variables
    riêng, xem `freshness.py`/`topic_affinity.py` — tách bạch intrinsic
    performance khỏi lý do giải thích, theo docs/claude/data-model.md "Metric
    Architecture"). Metric "shares" không tồn tại trong Threads API — loại khỏi
    công thức.
    """
    if insights.views == 0:
        return 0.0
    return (insights.reposts + insights.quotes) / insights.views * 100
