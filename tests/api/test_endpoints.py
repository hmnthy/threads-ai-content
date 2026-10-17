from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from httpx import Request, Response

from src.api.cache import Cache
from src.api.client import ThreadsAPIError, ThreadsClient
from src.api.endpoints import (
    PAGE_SIZE,
    POST_FIELDS,
    _paginate,
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
    # (re-requesting the edge with its `after` cursor) rather than stopping at the
    # first 25-ish results.
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
    second = route.calls[1].request.url.params
    assert second["after"] == "CURSOR1"
    assert second["limit"] == str(PAGE_SIZE)
    # Token chỉ 1 lần — không bơm thêm khi đi theo cursor
    assert second.get_list("access_token") == ["tok"]

    # Second call should be served from cache, not hit the API again.
    posts_again = await get_posts(client, "999", cache=cache)
    assert len(posts_again) == 2
    assert route.calls.call_count == 2
    await client.aclose()


def _post(post_id: str) -> dict[str, str]:
    return {"id": post_id, "timestamp": "2026-08-28T10:00:00+0000", "media_type": "TEXT_POST"}


# Shape thật của lỗi làm hỏng job snapshot 13→17/10/2026 (đo live 2026-10-17)
META_UNKNOWN_500 = {
    "error": {
        "message": "An unknown error has occurred.",
        "type": "OAuthException",
        "code": 1,
        "fbtrace_id": "TRACE",
    }
}


@respx.mock
async def test_server_error_halves_the_page_and_retries_the_same_cursor(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Trang sau CURSOR1 lỗi 500 ở limit 25 và 12, qua ở limit 6 — bài phải đủ, không
    # trùng, và trang sau đó quay lại cỡ đầy đủ.
    def respond(request: Request) -> Response:
        params = request.url.params
        after, limit = params.get("after"), int(params["limit"])
        if after is None:
            return Response(200, json={"data": [_post("1")], "paging": _next("CURSOR1")})
        if after == "CURSOR1":
            if limit > 6:
                return Response(500, json=META_UNKNOWN_500)
            return Response(200, json={"data": [_post("2")], "paging": _next("CURSOR2")})
        return Response(200, json={"data": [_post("3")]})

    route = respx.get(f"{BASE}/999/threads").mock(side_effect=respond)
    client = ThreadsClient(access_token="tok")

    posts = await get_posts(client, "999")

    assert [post.id for post in posts] == ["1", "2", "3"]
    params = [call.request.url.params for call in route.calls]
    calls = [(p.get("after"), p["limit"]) for p in params]
    assert calls == [
        (None, "25"),
        ("CURSOR1", "25"),
        ("CURSOR1", "12"),
        ("CURSOR1", "6"),
        ("CURSOR2", "25"),
    ]
    # 1 dòng tóm tắt cho cả edge, không phải 1 dòng mỗi lần lỗi
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "/999/threads: retried 2 server errors" in warnings[0]
    assert "fbtrace_id TRACE" in warnings[0]
    await client.aclose()


@respx.mock
async def test_client_error_is_not_retried() -> None:
    # 4xx (token hết hạn, tham số sai) thì thu nhỏ trang không chữa được — ném ngay.
    route = respx.get(f"{BASE}/999/threads").mock(
        return_value=Response(400, json={"error": {"message": "Invalid OAuth", "code": 190}})
    )
    client = ThreadsClient(access_token="tok")

    with pytest.raises(ThreadsAPIError) as exc_info:
        await get_posts(client, "999")

    assert exc_info.value.error_code == 190
    assert route.calls.call_count == 1
    await client.aclose()


@respx.mock
async def test_single_post_failing_with_children_is_fetched_without_then_children_alone(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Tái hiện bài `CAROUSEL_ALBUM` 2025-06-08 (1 ảnh con hỏng phía Meta): danh sách kèm
    # `children` lỗi 500 kể cả trang 1 bài, bỏ `children` thì qua; `children` gọi riêng bài
    # thì được → phải ghép lại thay vì để `raw_json` mất hết ảnh con (gọi riêng có thể vẫn
    # thiếu ảnh con hỏng — Meta không trả nó).
    def respond(request: Request) -> Response:
        if "children" in request.url.params["fields"].split(","):
            return Response(500, json=META_UNKNOWN_500)
        album = {**_post("42"), "media_type": "CAROUSEL_ALBUM"}
        return Response(200, json={"data": [album]})

    route = respx.get(f"{BASE}/999/threads").mock(side_effect=respond)
    single = respx.get(f"{BASE}/42").mock(
        return_value=Response(
            200, json={"id": "42", "children": {"data": [{"id": "c1"}, {"id": "c2"}]}}
        )
    )
    client = ThreadsClient(access_token="tok")

    posts = await get_posts(client, "999")

    assert [post.id for post in posts] == ["42"]
    assert posts[0].children == ["c1", "c2"]
    assert [c.request.url.params["limit"] for c in route.calls] == ["25", "12", "6", "3", "1", "1"]
    assert "children" not in route.calls.last.request.url.params["fields"].split(",")
    assert single.calls.last.request.url.params["fields"] == "children"
    # Log ghi số ảnh con lấy được — gọi riêng có thể thiếu ảnh con hỏng
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("post 42 fetched without children" in w and "2 children" in w for w in warnings)
    await client.aclose()


@respx.mock
async def test_fallback_in_the_middle_of_the_list_keeps_the_cursor() -> None:
    # Bài hỏng nằm giữa danh sách (thực tế: vị trí 158/159). Lần gọi bỏ `children` phải
    # giữ đúng cursor của trang lỗi — nếu rơi về trang đầu, phân trang sẽ quay lại bài hỏng
    # mãi (review 2026-10-17: test chỉ ở trang đầu không bắt được lỗi này).
    def respond(request: Request) -> Response:
        params = request.url.params
        after = params.get("after")
        with_children = "children" in params["fields"].split(",")
        if after is None:
            return Response(200, json={"data": [_post("1")], "paging": _next("CURSOR1")})
        if after == "CURSOR1":
            if with_children:
                return Response(500, json=META_UNKNOWN_500)
            album = {**_post("42"), "media_type": "CAROUSEL_ALBUM"}
            return Response(200, json={"data": [album], "paging": _next("CURSOR2")})
        return Response(200, json={"data": [_post("3")]})

    route = respx.get(f"{BASE}/999/threads").mock(side_effect=respond)
    respx.get(f"{BASE}/42").mock(
        return_value=Response(200, json={"id": "42", "children": {"data": [{"id": "c1"}]}})
    )
    client = ThreadsClient(access_token="tok")

    posts = await get_posts(client, "999")

    assert [post.id for post in posts] == ["1", "42", "3"]
    assert posts[1].children == ["c1"]
    reduced = [
        call.request.url.params
        for call in route.calls
        if "children" not in call.request.url.params["fields"].split(",")
    ]
    assert len(reduced) == 1
    assert reduced[0]["after"] == "CURSOR1"
    assert route.calls.last.request.url.params["after"] == "CURSOR2"
    await client.aclose()


def _album_list_fails_with_children(request: Request) -> Response:
    if "children" in request.url.params["fields"].split(","):
        return Response(500, json=META_UNKNOWN_500)
    album = {**_post("42"), "media_type": "CAROUSEL_ALBUM"}
    return Response(200, json={"data": [album]})


@respx.mock
async def test_own_children_fetch_failing_keeps_the_post_without_children(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Live 2026-10-17: gọi riêng `children` của bài hỏng cũng lỗi 500 ngẫu nhiên. Bài vẫn
    # phải vào kết quả (snapshot của mọi bài không chết theo 1 ảnh con hỏng), log ghi lại.
    respx.get(f"{BASE}/999/threads").mock(side_effect=_album_list_fails_with_children)
    respx.get(f"{BASE}/42").mock(return_value=Response(500, json=META_UNKNOWN_500))
    client = ThreadsClient(access_token="tok")

    posts = await get_posts(client, "999")

    assert [post.id for post in posts] == ["42"]
    assert posts[0].children == []
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("post 42" in w and "kept without children" in w for w in warnings)
    await client.aclose()


@respx.mock
async def test_own_children_fetch_client_error_is_raised() -> None:
    # 4xx khi gọi riêng (token, quyền) không phải lỗi tạm thời của Meta — ném ra.
    respx.get(f"{BASE}/999/threads").mock(side_effect=_album_list_fails_with_children)
    respx.get(f"{BASE}/42").mock(
        return_value=Response(400, json={"error": {"message": "Invalid OAuth", "code": 190}})
    )
    client = ThreadsClient(access_token="tok")

    with pytest.raises(ThreadsAPIError) as exc_info:
        await get_posts(client, "999")

    assert exc_info.value.error_code == 190
    await client.aclose()


@respx.mock
async def test_single_post_still_failing_without_children_raises() -> None:
    # Trang 1 bài vẫn lỗi cả khi đã bỏ `children` → ném lỗi (job dừng, log ghi lại),
    # không lặng lẽ bỏ sót bài.
    route = respx.get(f"{BASE}/999/threads").mock(return_value=Response(500, json=META_UNKNOWN_500))
    client = ThreadsClient(access_token="tok")

    with pytest.raises(ThreadsAPIError) as exc_info:
        await get_posts(client, "999")

    assert exc_info.value.status_code == 500
    # 25 → 12 → 6 → 3 → 1, rồi 1 lần bỏ `children`
    assert route.calls.call_count == 6
    assert "children" in POST_FIELDS.split(",")
    await client.aclose()


@respx.mock
async def test_single_post_failing_with_no_fallback_field_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Không có field nào trong `PER_ITEM_FALLBACK_FIELDS` để bỏ → ném lỗi gốc ngay ở trang
    # 1 bài; tóm tắt các lần thử lại vẫn được ghi (log có ngữ cảnh trước khi job chết).
    route = respx.get(f"{BASE}/999/threads").mock(return_value=Response(500, json=META_UNKNOWN_500))
    client = ThreadsClient(access_token="tok")

    with pytest.raises(ThreadsAPIError):
        await _paginate(client, "/999/threads", "id,text")

    assert [c.request.url.params["limit"] for c in route.calls] == ["25", "12", "6", "3", "1"]
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert warnings == [
        "/999/threads: retried 4 server errors with smaller pages (last: ThreadsAPIError: "
        "An unknown error has occurred. (HTTP 500, code 1, fbtrace_id TRACE))"
    ]
    await client.aclose()


@respx.mock
async def test_timeout_is_retried_like_a_server_error() -> None:
    # Trang quá nặng có thể làm Meta trả chậm quá timeout thay vì 500 — cùng nguyên nhân,
    # cùng cách chữa.
    def respond(request: Request) -> Response:
        if request.url.params["limit"] == "25":
            raise httpx.ReadTimeout("slow page", request=request)
        return Response(200, json={"data": [_post("1")]})

    route = respx.get(f"{BASE}/999/threads").mock(side_effect=respond)
    client = ThreadsClient(access_token="tok")

    posts = await get_posts(client, "999")

    assert [post.id for post in posts] == ["1"]
    assert [c.request.url.params["limit"] for c in route.calls] == ["25", "12"]
    await client.aclose()


@respx.mock
async def test_paging_next_without_after_cursor_stops_instead_of_looping() -> None:
    respx.get(f"{BASE}/999/threads").mock(
        return_value=Response(
            200, json={"data": [_post("1")], "paging": {"next": f"{BASE}/999/threads?limit=25"}}
        )
    )
    client = ThreadsClient(access_token="tok")

    with pytest.raises(ValueError, match="no `after` cursor"):
        await get_posts(client, "999")
    await client.aclose()


@respx.mock
async def test_paging_next_with_unknown_params_stops() -> None:
    # Meta thêm tham số mới vào `next` (VD phân trang theo thời gian) → dừng hẳn thay vì
    # gọi thiếu tham số mà không ai biết.
    next_url = f"{BASE}/999/threads?after=C1&until=123&access_token=tok"
    respx.get(f"{BASE}/999/threads").mock(
        return_value=Response(200, json={"data": [_post("1")], "paging": {"next": next_url}})
    )
    client = ThreadsClient(access_token="tok")

    with pytest.raises(ValueError, match=r"unexpected params \['until'\]"):
        await get_posts(client, "999")
    await client.aclose()


@respx.mock
async def test_repeated_cursor_stops_instead_of_looping() -> None:
    respx.get(f"{BASE}/999/threads").mock(
        side_effect=[
            Response(200, json={"data": [_post("1")], "paging": _next("SAME")}),
            Response(200, json={"data": [_post("2")], "paging": _next("SAME")}),
        ]
    )
    client = ThreadsClient(access_token="tok")

    with pytest.raises(ValueError, match="repeats an earlier cursor"):
        await get_posts(client, "999")
    await client.aclose()


@respx.mock
async def test_duplicate_post_is_skipped_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    # Bài trùng (VD cursor theo vị trí + bài mới đăng giữa lúc phân trang) trước đây vô hại
    # (upsert ghi đè cùng dòng) — không được làm job chết, chỉ bỏ qua và ghi lại.
    respx.get(f"{BASE}/999/threads").mock(
        side_effect=[
            Response(200, json={"data": [_post("1"), _post("2")], "paging": _next("C1")}),
            Response(200, json={"data": [_post("2"), _post("3")]}),
        ]
    )
    client = ThreadsClient(access_token="tok")

    posts = await get_posts(client, "999")

    assert [post.id for post in posts] == ["1", "2", "3"]
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert warnings == ["/999/threads: skipped 1 posts returned twice while paging"]
    await client.aclose()


@respx.mock
async def test_timeout_at_a_single_post_page_goes_to_the_fallback() -> None:
    # Timeout ở trang 1 bài kèm `children` → cùng đường fallback như 500.
    def respond(request: Request) -> Response:
        if "children" in request.url.params["fields"].split(","):
            raise httpx.ReadTimeout("", request=request)
        album = {**_post("42"), "media_type": "CAROUSEL_ALBUM"}
        return Response(200, json={"data": [album]})

    route = respx.get(f"{BASE}/999/threads").mock(side_effect=respond)
    respx.get(f"{BASE}/42").mock(
        return_value=Response(200, json={"id": "42", "children": {"data": [{"id": "c1"}]}})
    )
    client = ThreadsClient(access_token="tok")

    posts = await get_posts(client, "999")

    assert posts[0].children == ["c1"]
    assert [c.request.url.params["limit"] for c in route.calls] == ["25", "12", "6", "3", "1", "1"]
    await client.aclose()


@respx.mock
async def test_own_children_fetch_timeout_keeps_the_post(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Timeout ở lần gọi riêng → giữ bài như 5xx; log ghi tên loại lỗi vì thông điệp
    # timeout có thể rỗng.
    def own(request: Request) -> Response:
        raise httpx.ReadTimeout("", request=request)

    respx.get(f"{BASE}/999/threads").mock(side_effect=_album_list_fails_with_children)
    respx.get(f"{BASE}/42").mock(side_effect=own)
    client = ThreadsClient(access_token="tok")

    posts = await get_posts(client, "999")

    assert [post.id for post in posts] == ["42"]
    assert posts[0].children == []
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("failed too (ReadTimeout: )" in w for w in warnings)
    await client.aclose()


def _next(cursor: str) -> dict[str, str]:
    return {"next": f"{BASE}/999/threads?after={cursor}&limit=25&access_token=tok"}


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
