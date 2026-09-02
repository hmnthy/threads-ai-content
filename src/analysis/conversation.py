from __future__ import annotations

from src.api.models import PostInsights


def conversation_rate(insights: PostInsights) -> float:
    """replies / views * 100.

    CHỈ nhận `insights`. V2: nâng cấp bằng unique repliers/reply depth qua
    `ContentUnit` (xem docs/claude/data-model.md "Metric Architecture") — V1 chỉ
    dùng tổng số replies vì đó là field duy nhất post-level insights trả về.
    """
    if insights.views == 0:
        return 0.0
    return insights.replies / insights.views * 100
