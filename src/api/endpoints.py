from __future__ import annotations

from typing import Any, Final

from src.api.cache import Cache
from src.api.client import ThreadsClient
from src.api.models import AccountInsights, PostInsights, ThreadsPost, UserInfo

USER_FIELDS: Final = "id,username"
POST_FIELDS: Final = (
    "id,text,timestamp,media_type,permalink,shortcode,username,"
    "media_url,thumbnail_url,is_quote_post,quoted_post,reposted_post,children"
)
POST_INSIGHTS_METRICS: Final = "views,likes,replies,reposts,quotes"
# follower_demographics is deliberately excluded: confirmed live (2026-08-28) that Threads
# rejects it unless called separately with an explicit `breakdown` param — see
# get_follower_demographics() below.
ACCOUNT_INSIGHTS_METRICS: Final = "views,likes,replies,reposts,quotes,clicks,followers_count"
FOLLOWER_DEMOGRAPHICS_BREAKDOWNS: Final = ("country", "city", "age", "gender")


async def get_user_info(client: ThreadsClient, user_id: str) -> UserInfo:
    data = await client.get(f"/{user_id}", params={"fields": USER_FIELDS})
    return UserInfo.model_validate(data)


async def get_posts(
    client: ThreadsClient, user_id: str, cache: Cache | None = None
) -> list[ThreadsPost]:
    """Fetch all posts for user_id, serving from cache when available and fresh."""
    cache_key = f"posts_{user_id}"
    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            return [ThreadsPost.model_validate(item) for item in cached]

    data = await client.get(f"/{user_id}/threads", params={"fields": POST_FIELDS})
    posts = [ThreadsPost.model_validate(item) for item in data.get("data", [])]

    if cache is not None:
        cache.set(cache_key, [post.model_dump(mode="json") for post in posts])
    return posts


async def get_post_insights(client: ThreadsClient, post_id: str) -> PostInsights:
    data = await client.get(f"/{post_id}/insights", params={"metric": POST_INSIGHTS_METRICS})
    metrics = _flatten_insights(data)
    return PostInsights(post_id=post_id, **metrics)


async def get_account_insights(client: ThreadsClient, user_id: str) -> AccountInsights:
    data = await client.get(
        f"/{user_id}/threads_insights", params={"metric": ACCOUNT_INSIGHTS_METRICS}
    )
    metrics = _flatten_insights(data)
    return AccountInsights(**metrics)


async def get_follower_demographics(
    client: ThreadsClient, user_id: str, breakdown: str = "country"
) -> dict[str, Any]:
    """follower_demographics requires an explicit breakdown; confirmed live 2026-08-28
    that Meta rejects the metric entirely without one (error_subcode 4279040)."""
    if breakdown not in FOLLOWER_DEMOGRAPHICS_BREAKDOWNS:
        raise ValueError(f"breakdown must be one of {FOLLOWER_DEMOGRAPHICS_BREAKDOWNS}")
    data = await client.get(
        f"/{user_id}/threads_insights",
        params={"metric": "follower_demographics", "breakdown": breakdown},
    )
    metrics = _flatten_insights(data)
    result: dict[str, Any] = metrics.get("follower_demographics", {})
    return result


def _flatten_insights(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten the Graph Insights response shape into {metric_name: value}.

    Confirmed live against the real API (2026-08-28) that the shape is NOT uniform
    across metrics:
    - post-level metrics (period="lifetime"): `values: [{"value": N}]`, one entry
    - account-level "views" (period="day"): `values: [{"value": N}, ...]`, one entry
      per day in the queried window — summed here to get a period total
    - account-level likes/replies/reposts/quotes/followers_count: `total_value: {"value": N}`
    - "clicks": `link_total_values: [{"value": N, "link_url": ...}, ...]` — summed
    - "follower_demographics" (only when called with a `breakdown`): `total_value`
      is a breakdown dict with no "value" key, kept as-is
    """
    metrics: dict[str, Any] = {}
    for item in data.get("data", []):
        name = item["name"]
        if "total_value" in item:
            total_value = item["total_value"]
            metrics[name] = total_value.get("value", total_value)
        elif "link_total_values" in item:
            metrics[name] = sum(v["value"] for v in item["link_total_values"])
        elif "values" in item:
            metrics[name] = sum(v["value"] for v in item["values"])
    return metrics
