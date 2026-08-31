from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from src.api.models import PostInsights, ThreadsPost


def _insights_by_post_id(insights: list[PostInsights]) -> dict[str, PostInsights]:
    return {item.post_id: item for item in insights}


def average_engagement_rate(insights: list[PostInsights]) -> float:
    """Mean of PostInsights.engagement_rate across all given posts; 0.0 if empty."""
    if not insights:
        return 0.0
    return sum(item.engagement_rate for item in insights) / len(insights)


def top_posts_by_engagement(
    posts: list[ThreadsPost], insights: list[PostInsights], limit: int = 10
) -> list[tuple[ThreadsPost, PostInsights]]:
    """Posts paired with their insights, sorted by engagement rate descending.

    Posts with no matching insights (by id) are skipped.
    """
    by_id = _insights_by_post_id(insights)
    paired = [(post, by_id[post.id]) for post in posts if post.id in by_id]
    return sorted(paired, key=lambda pair: pair[1].engagement_rate, reverse=True)[:limit]


def engagement_by_hour(
    posts: list[ThreadsPost], insights: list[PostInsights], *, timezone: ZoneInfo | None = None
) -> dict[int, float]:
    """Average engagement rate bucketed by post hour (0-23).

    Threads timestamps are UTC. Pass `timezone` (e.g. ZoneInfo("Europe/Paris") or
    ZoneInfo("Asia/Ho_Chi_Minh")) to bucket by that zone's local hour instead —
    call this once per audience timezone to compare them, since Threads doesn't
    expose which timezone/country any given engagement actually came from.
    """
    return _bucket_average(
        posts, insights, key=lambda post: _localize(post.timestamp, timezone).hour
    )


def engagement_by_weekday(
    posts: list[ThreadsPost], insights: list[PostInsights], *, timezone: ZoneInfo | None = None
) -> dict[int, float]:
    """Average engagement rate bucketed by weekday (0=Monday .. 6=Sunday).

    Threads timestamps are UTC. Pass `timezone` to bucket by that zone's local
    weekday instead — matters near local midnight, where a post can fall on a
    different calendar day once converted (see engagement_by_hour)."""
    return _bucket_average(
        posts, insights, key=lambda post: _localize(post.timestamp, timezone).weekday()
    )


def _localize(timestamp: datetime, timezone: ZoneInfo | None) -> datetime:
    return timestamp if timezone is None else timestamp.astimezone(timezone)


def _bucket_average(
    posts: list[ThreadsPost],
    insights: list[PostInsights],
    *,
    key: Callable[[ThreadsPost], int],
) -> dict[int, float]:
    by_id = _insights_by_post_id(insights)
    buckets: dict[int, list[float]] = defaultdict(list)
    for post in posts:
        item = by_id.get(post.id)
        if item is not None:
            buckets[key(post)].append(item.engagement_rate)
    return {bucket: sum(rates) / len(rates) for bucket, rates in buckets.items()}
