from __future__ import annotations

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
