from datetime import date
from pathlib import Path

import pytest
import respx
from httpx import Response

from src.api.cache import Cache
from src.api.client import ThreadsClient
from src.api.endpoints import (
    get_account_daily_views,
    get_account_insights,
    get_follower_demographics,
    get_post_insights,
    get_posts,
    get_replies,
    get_user_info,
)

BASE = "https://graph.threads.net/v1.0"


@respx.mock
async def test_get_user_info_parses_response() -> None:
    respx.get(f"{BASE}/999").mock(
        return_value=Response(200, json={"id": "999", "username": "thydilammuon"})
    )
    client = ThreadsClient(access_token="tok")

    info = await get_user_info(client, "999")

    assert info.id == "999"
    assert info.username == "thydilammuon"
    await client.aclose()


@respx.mock
async def test_get_posts_follows_pagination_across_full_channel_history(
    tmp_path: Path,
) -> None:
    # First page reports a `paging.next` cursor link; get_posts() must follow it
    # (via ThreadsClient.get_url) rather than stopping at the first 25-ish results.
    route = respx.get(f"{BASE}/999/threads").mock(
        side_effect=[
            Response(
                200,
                json={
                    "data": [
                        {
                            "id": "1",
                            "timestamp": "2026-08-28T10:00:00+0000",
                            "media_type": "TEXT_POST",
                        }
                    ],
                    "paging": {
                        "next": f"{BASE}/999/threads?after=CURSOR1&access_token=tok",
                    },
                },
            ),
            Response(
                200,
                json={
                    "data": [
                        {
                            "id": "2",
                            "timestamp": "2026-08-27T10:00:00+0000",
                            "media_type": "TEXT_POST",
                        }
                    ]
                    # No `paging.next` here — this is the last page.
                },
            ),
        ]
    )
    client = ThreadsClient(access_token="tok")
    cache = Cache(cache_dir=tmp_path)

    posts = await get_posts(client, "999", cache=cache)

    assert [post.id for post in posts] == ["1", "2"]
    assert route.calls.call_count == 2

    # Second call should be served from cache, not hit the API again.
    posts_again = await get_posts(client, "999", cache=cache)
    assert len(posts_again) == 2
    assert route.calls.call_count == 2
    await client.aclose()


@respx.mock
async def test_get_replies_returns_parsed_list_and_caches_separately_from_posts(
    tmp_path: Path,
) -> None:
    route = respx.get(f"{BASE}/999/replies").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": "reply-1",
                        "timestamp": "2026-08-28T10:00:00+0000",
                        "media_type": "TEXT_POST",
                    }
                ]
            },
        )
    )
    client = ThreadsClient(access_token="tok")
    cache = Cache(cache_dir=tmp_path)

    replies = await get_replies(client, "999", cache=cache)

    assert len(replies) == 1
    assert replies[0].id == "reply-1"
    assert route.calls.call_count == 1

    # Cached under its own key — must not collide with (or be served by) get_posts()'s cache.
    replies_again = await get_replies(client, "999", cache=cache)
    assert len(replies_again) == 1
    assert route.calls.call_count == 1
    assert cache.get("posts_999") is None
    await client.aclose()


@respx.mock
async def test_get_post_insights_flattens_time_series_metrics() -> None:
    respx.get(f"{BASE}/post-1/insights").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {"name": "views", "values": [{"value": 1000}]},
                    {"name": "likes", "values": [{"value": 80}]},
                    {"name": "replies", "values": [{"value": 10}]},
                    {"name": "reposts", "values": [{"value": 5}]},
                    {"name": "quotes", "values": [{"value": 2}]},
                ]
            },
        )
    )
    client = ThreadsClient(access_token="tok")

    insights = await get_post_insights(client, "post-1")

    assert insights.post_id == "post-1"
    assert insights.views == 1000
    assert insights.likes == 80
    await client.aclose()


@respx.mock
async def test_get_account_insights_matches_real_api_shapes() -> None:
    # Shapes confirmed live against the real Threads API on 2026-08-28: "views" is a
    # per-day time series (summed here for a period total), likes/replies/reposts/
    # quotes/followers_count come back as total_value.value, and clicks is a
    # per-link breakdown (link_total_values) rather than a single number.
    respx.get(f"{BASE}/999/threads_insights").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "name": "views",
                        "period": "day",
                        "values": [{"value": 6211}, {"value": 1995}],
                    },
                    {"name": "likes", "total_value": {"value": 23}},
                    {"name": "replies", "total_value": {"value": 4}},
                    {"name": "reposts", "total_value": {"value": 0}},
                    {"name": "quotes", "total_value": {"value": 0}},
                    {"name": "followers_count", "total_value": {"value": 1398}},
                    {
                        "name": "clicks",
                        "link_total_values": [
                            {"value": 3, "link_url": "https://a.example"},
                            {"value": 5, "link_url": "https://b.example"},
                        ],
                    },
                ]
            },
        )
    )
    client = ThreadsClient(access_token="tok")

    insights = await get_account_insights(client, "999")

    assert insights.views == 6211 + 1995
    assert insights.likes == 23
    assert insights.followers_count == 1398
    assert insights.clicks == 3 + 5
    await client.aclose()


@respx.mock
async def test_get_follower_demographics_requires_breakdown_param_in_request() -> None:
    route = respx.get(f"{BASE}/999/threads_insights").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "name": "follower_demographics",
                        "total_value": {
                            "breakdowns": [
                                {
                                    "dimension_keys": ["country"],
                                    "results": [{"dimension_values": ["VN"], "value": 900}],
                                }
                            ]
                        },
                    }
                ]
            },
        )
    )
    client = ThreadsClient(access_token="tok")

    result = await get_follower_demographics(client, "999", breakdown="country")

    assert route.calls.last.request.url.params["breakdown"] == "country"
    assert result["breakdowns"][0]["dimension_keys"] == ["country"]
    await client.aclose()


async def test_get_follower_demographics_rejects_invalid_breakdown() -> None:
    client = ThreadsClient(access_token="tok")
    with pytest.raises(ValueError, match="breakdown must be one of"):
        await get_follower_demographics(client, "999", breakdown="not-a-real-one")
    await client.aclose()


@respx.mock
async def test_get_account_daily_views_keeps_each_day_separate_and_converts_end_time() -> None:
    # Shape confirmed live against the real API 2026-09-03: end_time always lands on
    # "07:00:00+0000" — a Pacific-time day boundary, one calendar day AHEAD of the
    # day the value actually belongs to (see get_account_daily_views docstring).
    respx.get(f"{BASE}/999/threads_insights").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "name": "views",
                        "period": "day",
                        "values": [
                            {"value": 18, "end_time": "2025-07-29T07:00:00+0000"},
                            {"value": 6, "end_time": "2025-07-30T07:00:00+0000"},
                        ],
                    }
                ]
            },
        )
    )
    client = ThreadsClient(access_token="tok")

    points = await get_account_daily_views(client, "999", date(2025, 7, 28), date(2025, 7, 29))

    assert [p.date for p in points] == ["2025-07-28", "2025-07-29"]
    assert [p.views for p in points] == [18, 6]
    await client.aclose()


@respx.mock
async def test_get_account_daily_views_sends_since_and_until_params() -> None:
    route = respx.get(f"{BASE}/999/threads_insights").mock(
        return_value=Response(200, json={"data": [{"name": "views", "values": []}]})
    )
    client = ThreadsClient(access_token="tok")

    await get_account_daily_views(client, "999", date(2025, 1, 1), date(2025, 1, 31))

    params = route.calls.last.request.url.params
    assert params["metric"] == "views"
    assert params["period"] == "day"
    assert params["since"] == "2025-01-01"
    assert params["until"] == "2025-01-31"
    await client.aclose()
