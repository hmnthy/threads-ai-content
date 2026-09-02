from __future__ import annotations

from src.api.models import PostInsights


def popularity_index(insights: PostInsights) -> int:
    """views — Threads không có reach/impressions, đây là proxy tốt nhất đã verify
    (xem docs/claude/data-model.md "Metric Architecture"). Intrinsic metric thuần
    tuý — KHÔNG nhận post/age/topic."""
    return insights.views
